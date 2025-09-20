import json
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseRedirect, QueryDict
from django.http.response import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import redirect, reverse
from django.template.loader import render_to_string
from django.utils.cache import add_never_cache_headers
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)
from rest_framework.mixins import CreateModelMixin
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import GenericViewSet

from peachjam.models import Author, CourtRegistry, Judge, Label, pj_settings
from peachjam.resources import DownloadDocumentsResource
from peachjam_api.serializers import LabelSerializer
from peachjam_search.engine import SearchEngine
from peachjam_search.forms import (
    SavedSearchCreateForm,
    SavedSearchUpdateForm,
    SearchFeedbackCreateForm,
    SearchForm,
)
from peachjam_search.models import SavedSearch, SearchTrace
from peachjam_search.serializers import SearchClickSerializer, SearchHit

CACHE_SECS = 15 * 60
SUGGESTIONS_CACHE_SECS = 60 * 60 * 6


class SearchView(TemplateView):
    template_name = "peachjam_search/search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_placeholder_text = _("Search %(app_name)s") % {
            "app_name": settings.PEACHJAM["APP_NAME"]
        }
        context["labels"] = {
            "author": Author.model_label,
            "registry": CourtRegistry.model_label,
            "judge": Judge.model_label_plural,
            "searchPlaceholder": search_placeholder_text,
            "documentLabels": LabelSerializer(Label.objects.all(), many=True).data,
        }
        context["show_jurisdiction"] = settings.PEACHJAM["SEARCH_JURISDICTION_FILTER"]
        return context


class DocumentSearchView(TemplateView):
    http_method_names = ["get"]
    action = "search"
    template_name = "peachjam_search/search_request_debug.html"
    config_version = "2025-07-28"

    def get(self, request, *args, **kwargs):
        return getattr(self, self.action)(request, *args, **kwargs)

    @vary_on_cookie
    @method_decorator(cache_page(CACHE_SECS))
    def search(self, request, *args, **kwargs):
        form = SearchForm(request.GET)
        if not form.is_valid():
            return JsonResponse({"error": form.errors}, status=400)

        engine = self.make_search_engine(form)

        if not engine.query and not engine.field_queries:
            # no search term
            return JsonResponse({"error": "No search term"}, status=400)

        # download as xlsx
        if self.request.GET.get("format"):
            return self.download_results(engine, self.request.GET["format"])

        es_response = engine.execute()
        trace = self.save_search_trace(engine, es_response.hits.total.value)

        hits = SearchHit.from_es_hits(engine, es_response.hits)
        SearchHit.attach_documents(hits)
        # only keep those with documents
        hits = [h for h in hits if h.document]

        response = {
            "count": es_response.hits.total.value,
            "facets": es_response.aggregations.to_dict(),
            "results_html": render_to_string(
                "peachjam_search/_search_hit_list.html",
                {
                    "request": request,
                    "hits": hits,
                    "can_debug": self.request.user.has_perm(
                        "peachjam_search.debug_search"
                    ),
                    "show_jurisdiction": settings.PEACHJAM[
                        "SEARCH_JURISDICTION_FILTER"
                    ],
                },
            ),
            "trace_id": str(trace.id) if trace else None,
            "can_download": self.request.user.has_perm(
                "peachjam_search.download_search"
            ),
            "can_semantic": settings.PEACHJAM["SEARCH_SEMANTIC"],
        }

        return self.render(response)

    @method_decorator(cache_page(SUGGESTIONS_CACHE_SECS))
    def suggest(self, request, *args, **kwargs):
        q = request.GET.get("q")
        suggestions = []

        if q and settings.PEACHJAM["SEARCH_SUGGESTIONS"]:
            suggestions = SearchEngine().suggest(q).suggest.to_dict()
            suggestions["prefix"] = suggestions["prefix"][0]

        response = {"suggestions": suggestions}
        return self.render(response)

    @vary_on_cookie
    @method_decorator(cache_page(CACHE_SECS))
    def facets(self, request, *args, **kwargs):
        """Only return facets from search."""
        form = SearchForm(request.GET)
        if not form.is_valid():
            return JsonResponse({"error": form.errors}, status=400)

        form.cleaned_data["facets"] = True
        engine = self.make_search_engine(form)
        if not engine.query and not engine.field_queries:
            # no search term
            return JsonResponse({"error": "No search term"}, status=400)

        engine.page_size = 0
        es_response = engine.execute()

        return self.render(
            {
                "count": es_response.hits.total.value,
                "facets": es_response.aggregations.to_dict(),
            }
        )

    def make_search_engine(self, form):
        engine = SearchEngine()
        form.configure_engine(engine)

        engine.explain = self.request.user.has_perm("peachjam_search.debug_search")
        if settings.PEACHJAM["SEARCH_SEMANTIC"]:
            engine.mode = form.cleaned_data.get("mode") or engine.mode

        return engine

    def render(self, response):
        if "html" in self.request.GET:
            # useful for debugging and showing django debug panel details
            return self.render_to_response(
                {"response_json": json.dumps(response, indent=2)}
            )
        return JsonResponse(response)

    def save_search_trace(self, engine, n_results):
        filters_string = "; ".join(f"{k}={v}" for k, v in engine.filters.items())

        search = self.request.GET.get("search", "")[:2048]
        # ignore nulls
        search = search.replace("\00", " ")

        # save the search trace
        return SearchTrace.objects.create(
            user=self.request.user if self.request.user.is_authenticated else None,
            config_version=self.config_version,
            request_id=self.request.id if self.request.id != "none" else None,
            mode=engine.mode,
            search=search,
            field_searches=engine.field_queries,
            n_results=n_results,
            page=engine.page,
            filters=engine.filters,
            filters_string=filters_string,
            ordering=self.request.GET.get("ordering"),
            suggestion=self.request.GET.get("suggestion"),
            ip_address=self.request.headers.get("x-forwarded-for"),
            user_agent=self.request.headers.get("user-agent"),
        )

    def download_results(self, engine, format):
        if not self.request.user.has_perm("peachjam_search.download_search"):
            return HttpResponseForbidden()

        if format not in DownloadDocumentsResource.download_formats:
            return HttpResponseBadRequest("Invalid format")

        # only need the ids
        engine.source = ["_id"]
        engine.explain = False
        # TODO: first 1000 hits
        engine.page = 1
        engine.page_size = 1000
        response = engine.execute()
        pks = [int(hit.meta.id) for hit in response.hits]

        dataset = DownloadDocumentsResource().export(
            DownloadDocumentsResource.get_objects_for_download(pks)
        )
        fmt = DownloadDocumentsResource.download_formats[format]()
        data = fmt.export_data(dataset)

        response = HttpResponse(data, content_type=fmt.get_content_type())
        # prevent caching, so that we can enforce download permissions
        add_never_cache_headers(response)

        fname = "search-results." + fmt.get_extension()
        response["Content-Disposition"] = f'attachment; filename="{fname}"'

        return response


class SearchClickViewSet(CreateModelMixin, GenericViewSet):
    permission_classes = (AllowAny,)
    serializer_class = SearchClickSerializer


class SearchTraceListView(PermissionRequiredMixin, ListView):
    model = SearchTrace
    paginate_by = 50
    context_object_name = "traces"

    def get(self, request, *args, **kwargs):
        if request.GET.get("id"):
            # try to find this trace and redirect to the detail view if it exists,
            # otherwise show the list
            try:
                trace = SearchTrace.objects.filter(pk=request.GET["id"]).first()
                if trace:
                    return redirect("search:search_trace", pk=trace.pk)
            except ValidationError:
                pass
            messages.warning(request, _("Search trace not found"))
            return redirect("search:search_traces")
        return super().get(request, *args, **kwargs)

    def has_permission(self):
        return self.request.user.is_authenticated and self.request.user.is_staff


class SearchTraceDetailView(PermissionRequiredMixin, DetailView):
    model = SearchTrace
    queryset = SearchTrace.objects.prefetch_related("previous_search", "next_searches")
    context_object_name = "trace"

    def get(self, request, *args, **kwargs):
        trace = self.get_object()
        # walk the previous searches chain to find the first one
        ids = set()
        if trace.previous_search:
            original_trace = trace
            while trace.previous_search and trace.id not in ids:
                trace = trace.previous_search
                ids.add(trace.id)
            url = (
                reverse("search:search_trace", kwargs={"pk": trace.pk})
                + f"#{original_trace.pk}"
            )
            return redirect(url, pk=trace.pk)
        return super().get(request, *args, **kwargs)

    def has_permission(self):
        return self.request.user.is_authenticated and self.request.user.is_staff


class AllowSavedSearchesMixin:
    def dispatch(self, *args, **kwargs):
        if not pj_settings().allow_save_searches:
            raise Http404("Saving searches is not allowed.")
        return super().dispatch(*args, **kwargs)


class SavedSearchButtonView(AllowSavedSearchesMixin, TemplateView):
    template_name = "peachjam_search/saved_search_button.html"

    def get(self, *args, **kwargs):
        if self.request.user.is_authenticated and self.request.htmx:
            params = dict(
                QueryDict(urlparse(self.request.htmx.current_url_abs_path).query)
            )
            # these are fields we don't want to store
            params.pop("suggestion", None)
            params.pop("page", None)

            q = params.pop("q", "")
            a = params.pop("a", "")
            q = q[0] if q else ""
            a = a[0] if a else ""
            filters = SavedSearch(
                filters=urlencode(params, doseq=True)
            ).get_sorted_filters_string()
            saved_search = SavedSearch.objects.filter(
                Q(q=q) | Q(a=a), user=self.request.user, filters=filters
            ).first()
            if saved_search:
                # already exists, the update view handles editing
                return HttpResponseRedirect(
                    reverse(
                        "search:saved_search_update", kwargs={"pk": saved_search.pk}
                    )
                )
            else:
                self.extra_context = {
                    "saved_search": SavedSearch(
                        user=self.request.user,
                        q=q,
                        a=a,
                        filters=filters,
                    )
                }
        return super().get(*args, **kwargs)


class BaseSavedSearchFormView(
    AllowSavedSearchesMixin, LoginRequiredMixin, PermissionRequiredMixin
):
    model = SavedSearch
    context_object_name = "saved_search"

    def get_queryset(self):
        return self.request.user.saved_searches.all()

    def get_success_url(self):
        return reverse(
            "search:saved_search_update",
            kwargs={
                "pk": self.object.pk,
            },
        )


class SavedSearchCreateView(BaseSavedSearchFormView, CreateView):
    permission_required = "peachjam_search.add_savedsearch"
    template_name = "peachjam_search/saved_search_form.html"
    form_class = SavedSearchCreateForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        instance = SavedSearch()
        instance.user = self.request.user
        instance.last_alerted_at = now()
        instance.q = self.request.GET.get("q", "")
        instance.a = self.request.GET.get("a", "")
        instance.filters = self.request.GET.urlencode()
        instance.filters = instance.get_sorted_filters_string()
        kwargs["instance"] = instance
        return kwargs


class SavedSearchUpdateView(BaseSavedSearchFormView, UpdateView):
    permission_required = "peachjam_search.change_savedsearch"
    template_name = "peachjam_search/saved_search_form.html"
    form_class = SavedSearchUpdateForm


class SavedSearchListView(BaseSavedSearchFormView, ListView):
    permission_required = "peachjam_search.view_savedsearch"
    template_name = "peachjam_search/saved_search_list.html"
    context_object_name = "saved_searches"
    tab = "saved_searches"


class SavedSearchDeleteView(BaseSavedSearchFormView, DeleteView):
    permission_required = "peachjam_search.delete_savedsearch"

    def get_success_url(self):
        return self.request.GET.get("next", None) or reverse("search:saved_search_list")


class SearchFeedbackCreateView(View):
    form_class = SearchFeedbackCreateForm
    http_method_names = ["post"]

    def post(self, *args, **kwargs):
        form = self.form_class(self.request.POST)
        if form.is_valid():
            if self.request.user.is_authenticated:
                form.instance.user = self.request.user
            form.save()
            return HttpResponse()
        return HttpResponse(status=400)


class LinkTracesView(View):
    """This view allows the API to link new search trace to its preceding search, which we can't do directly
    when the search is executed because caching would get in the way. Instead, the search response includes a new
    trace ID and the frontend calls this to link the old and new search traces.
    """

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        previous_id = request.GET.get("previous")
        new_id = request.GET.get("new")

        if not previous_id or not new_id or previous_id == new_id:
            return HttpResponseBadRequest()

        try:
            previous_trace = SearchTrace.objects.get(pk=previous_id)
            # prevent loops caused by re-use trace-ids and caching, by ensuring we only go forwards in time
            new_trace = SearchTrace.objects.get(
                pk=new_id,
                previous_search=None,
                created_at__gte=previous_trace.created_at,
            )
        except ValidationError:
            return HttpResponseBadRequest()
        except SearchTrace.DoesNotExist:
            return HttpResponseBadRequest()

        if new_trace and previous_trace:
            new_trace.previous_search = previous_trace
            new_trace.save()

        return HttpResponse()
