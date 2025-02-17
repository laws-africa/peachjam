import json
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect, QueryDict
from django.http.response import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, reverse
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
from rest_framework.exceptions import PermissionDenied
from rest_framework.mixins import CreateModelMixin
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import GenericViewSet

from peachjam.models import Author, CourtRegistry, Judge, Label, pj_settings
from peachjam_api.serializers import LabelSerializer
from peachjam_search.engine import SearchEngine
from peachjam_search.forms import (
    SavedSearchCreateForm,
    SavedSearchUpdateForm,
    SearchFeedbackCreateForm,
    SearchForm,
)
from peachjam_search.models import SavedSearch, SearchTrace
from peachjam_search.serializers import (
    SearchableDocumentSerializer,
    SearchClickSerializer,
)

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
    config_version = "2024-10-31"

    def get(self, request, *args, **kwargs):
        return getattr(self, self.action)(request, *args, **kwargs)

    @vary_on_cookie
    @method_decorator(cache_page(CACHE_SECS))
    def search(self, request, *args, **kwargs):
        form = SearchForm(request.GET)
        if not form.is_valid():
            return JsonResponse({"error": form.errors}, status=400)

        engine = self.make_search_engine(request, form)
        es_response = engine.execute()

        if not engine.query and not engine.field_queries:
            # no search term
            return JsonResponse({"error": "No search term"}, status=400)

        results = SearchableDocumentSerializer(
            es_response.hits, many=True, context={"request": request}
        ).data

        response = {
            "count": es_response.hits.total.value,
            "results": results,
            "facets": es_response.aggregations.to_dict(),
        }

        trace = self.save_search_trace(engine, response)

        # show debug information to this user
        response["can_debug"] = self.request.user.has_perm("peachjam.can_debug_search")
        response["trace_id"] = trace.id if trace else None

        return self.render(response)

    def explain(self, request, pk, *args, **kwargs):
        if not request.user.has_perm("peachjam.can_debug_search"):
            raise PermissionDenied()

        form = SearchForm(request.GET)
        if not form.is_valid():
            return JsonResponse({"error": form.errors}, status=400)

        engine = self.make_search_engine(request, form)
        # the index must be passed in as a query param otherwise we don't know which one to use
        engine.index = request.GET.get("index") or engine.index
        es_response = engine.explain(pk)

        return self.render(es_response)

    @method_decorator(cache_page(SUGGESTIONS_CACHE_SECS))
    def suggest(self, request, *args, **kwargs):
        q = request.GET.get("q")
        suggestions = []

        if q and settings.PEACHJAM["SEARCH_SUGGESTIONS"]:
            suggestions = self.get_search_engine().suggest(q).suggest.to_dict()
            suggestions["prefix"] = suggestions["prefix"][0]

        response = {"suggestions": suggestions}
        return self.render(response)

    def get_search_engine(self):
        return SearchEngine()

    def make_search_engine(self, request, form):
        engine = self.get_search_engine()
        engine.query = form.cleaned_data.get("search")
        engine.page = form.cleaned_data.get("page") or 1
        engine.ordering = form.cleaned_data.get("ordering") or engine.ordering

        engine.filters = {}
        for key in request.GET.keys():
            if key in engine.filter_fields:
                engine.filters[key] = request.GET.getlist(key)

        # date ranges handled separately
        date = form.cleaned_data.get("date")
        if date:
            engine.filters["date"] = date

        engine.field_queries = {}
        for field in list(engine.advanced_search_fields.keys()) + ["all"]:
            val = (request.GET.get(f"search__{field}") or "").strip()
            if val:
                engine.field_queries[field] = val

        return engine

    def render(self, response):
        if "html" in self.request.GET:
            # useful for debugging and showing django debug panel details
            return self.render_to_response(
                {"response_json": json.dumps(response, indent=2)}
            )
        return JsonResponse(response)

    def save_search_trace(self, engine, response):
        # don't save search traces for alerts
        # TODO
        if "search-alert" in self.request.id:
            return

        filters_string = "; ".join(f"{k}={v}" for k, v in engine.filters.items())

        previous = None
        if self.request.GET.get("previous"):
            try:
                previous = SearchTrace.objects.filter(
                    pk=self.request.GET["previous"]
                ).first()
            except ValidationError:
                # ignore badly formed previous search ids
                pass

        search = self.request.GET.get("search", "")[:2048]
        # ignore nulls
        search = search.replace("\00", " ")

        # save the search trace
        return SearchTrace.objects.create(
            user=self.request.user if self.request.user.is_authenticated else None,
            config_version=self.config_version,
            request_id=self.request.id if self.request.id != "none" else None,
            search=search,
            field_searches=engine.field_queries,
            n_results=response["count"],
            page=engine.page,
            filters=engine.filters,
            filters_string=filters_string,
            ordering=self.request.GET.get("ordering"),
            previous_search=previous,
            suggestion=self.request.GET.get("suggestion"),
            ip_address=self.request.headers.get("x-forwarded-for"),
            user_agent=self.request.headers.get("user-agent"),
        )


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
        if trace.previous_search:
            original_trace = trace
            while trace.previous_search:
                trace = trace.previous_search
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
            q = q[0] if q else ""
            filters = SavedSearch(
                filters=urlencode(params, doseq=True)
            ).get_sorted_filters_string()
            saved_search = SavedSearch.objects.filter(
                user=self.request.user, q=q, filters=filters
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
