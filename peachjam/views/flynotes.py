import json

from django import forms
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import TrigramSimilarity
from django.core.exceptions import ValidationError
from django.db import ProgrammingError, transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Coalesce
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import DetailView, TemplateView

from peachjam.models.flynote import Flynote
from peachjam.views.judgment import FlynoteViewMixin


class FlynoteManagerForm(forms.ModelForm):
    class Meta:
        model = Flynote
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
        }


@method_decorator(staff_member_required, name="dispatch")
class FlynoteManagerView(TemplateView):
    template_name = "peachjam/flynote/manager/manager.html"


class FlynoteManagerMixin(FlynoteViewMixin):
    model = Flynote
    new_flynote_window = timezone.timedelta(days=2)

    def get_flynote_content_type(self):
        return ContentType.objects.get_for_model(Flynote)

    def log_flynote_change(self, request, flynote, message):
        LogEntry.objects.log_action(
            user_id=request.user.pk,
            content_type_id=self.get_flynote_content_type().pk,
            object_id=flynote.pk,
            object_repr=str(flynote)[:200],
            action_flag=CHANGE,
            change_message=message,
        )

    def get_queryset(self):
        return self.model.objects.select_related("document_count_cache")

    def deprecated_only(self):
        return self.request.GET.get("deprecated") == "true"

    def filter_deprecated_queryset(self, queryset):
        if self.deprecated_only():
            return queryset.filter(deprecated=True)
        return queryset.filter(deprecated=False)

    def get_visible_children(self, flynote):
        return self.filter_deprecated_queryset(flynote.get_children())

    def serialize_node(self, flynote):
        try:
            document_count = flynote.document_count_cache.count
        except Flynote.document_count_cache.RelatedObjectDoesNotExist:
            document_count = 0
        numchild = self.get_visible_children(flynote).count()
        has_children = numchild > 0
        is_new_root = (
            flynote.depth == 1
            and flynote.created_at >= timezone.now() - self.new_flynote_window
        )

        return {
            "id": flynote.pk,
            "name": flynote.name,
            "deprecated": flynote.deprecated,
            "is_new": is_new_root,
            "numchild": numchild,
            "document_count": document_count,
            "has_children": has_children,
        }

    def get_flynote_path_labels(self, flynotes):
        paths = set()
        for flynote in flynotes:
            for end in range(
                flynote.steplen,
                len(flynote.path) + 1,
                flynote.steplen,
            ):
                paths.add(flynote.path[:end])

        path_names = {
            flynote.path: flynote.name
            for flynote in Flynote.objects.filter(path__in=paths).only("name", "path")
        }
        return {
            flynote.pk: [
                path_names[path]
                for path in [
                    flynote.path[:end]
                    for end in range(
                        flynote.steplen,
                        len(flynote.path) + 1,
                        flynote.steplen,
                    )
                ]
                if path in path_names
            ]
            for flynote in flynotes
        }

    def get_merge_selected_ids(self, params):
        selected_ids = []
        for value in params.getlist("selected"):
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
            if value not in selected_ids:
                selected_ids.append(value)
        return selected_ids

    def get_merge_candidates(self, target, query, selected_ids):
        if target.is_root():
            qs = Flynote.get_root_nodes()
        else:
            qs = target.get_parent().get_children()

        qs = (
            qs.exclude(pk=target.pk)
            .exclude(pk__in=selected_ids)
            .select_related("document_count_cache")
            .annotate(document_total=Coalesce("document_count_cache__count", 0))
        )

        if query:
            trigram_qs = (
                qs.annotate(similarity=TrigramSimilarity("name", query))
                .filter(Q(similarity__gt=0.05) | Q(name__icontains=query))
                .order_by("-similarity", "-document_total", "name")
            )
            try:
                with transaction.atomic():
                    return list(trigram_qs[:50])
            except ProgrammingError:
                qs = qs.filter(name__icontains=query)

        return list(qs.order_by("-document_total", "name")[:50])

    def get_merge_picker_context(self, request, target, query, selected_ids):
        selected_flynotes = list(
            Flynote.objects.filter(pk__in=selected_ids)
            .select_related("document_count_cache")
            .annotate(document_total=Coalesce("document_count_cache__count", 0))
            .order_by("name")
        )
        selected_ids = [flynote.pk for flynote in selected_flynotes]

        search_results = self.get_merge_candidates(target, query, selected_ids)
        child_names = self.get_top_children_by_count(
            [*selected_flynotes, *search_results]
        )

        return {
            "target_flynote": target,
            "query": query,
            "selected_ids": selected_ids,
            "selected_flynotes": selected_flynotes,
            "search_results": search_results,
            "child_names": child_names,
            "picker_url": reverse("flynote-manager-merge-picker", args=[target.pk]),
            "merge_url": reverse("flynote-manager-merge", args=[target.pk]),
            "manager_url": reverse("flynote-manager"),
        }


@method_decorator(staff_member_required, name="dispatch")
class FlynoteManagerTreeView(FlynoteManagerMixin, View):
    def get(self, request, *args, **kwargs):
        flynotes = self.filter_deprecated_queryset(Flynote.get_root_nodes())
        flynotes = flynotes.select_related("document_count_cache").order_by("name")
        return JsonResponse({"results": [self.serialize_node(f) for f in flynotes]})


@method_decorator(staff_member_required, name="dispatch")
class FlynoteManagerTreeChildrenView(FlynoteManagerMixin, View):
    def get(self, request, *args, **kwargs):
        parent = get_object_or_404(Flynote, pk=kwargs["pk"])
        flynotes = self.get_visible_children(parent)
        flynotes = flynotes.select_related("document_count_cache").order_by("name")
        return JsonResponse({"results": [self.serialize_node(f) for f in flynotes]})


@method_decorator(staff_member_required, name="dispatch")
class FlynoteManagerTreePathView(View):
    def get(self, request, *args, **kwargs):
        flynote = get_object_or_404(Flynote, pk=kwargs["pk"])
        path_ids = list(
            Flynote.objects.filter(
                path__in=[
                    flynote.path[:end]
                    for end in range(
                        flynote.steplen,
                        len(flynote.path) + 1,
                        flynote.steplen,
                    )
                ]
            )
            .order_by("path")
            .values_list("pk", flat=True)
        )
        return JsonResponse({"path": path_ids})


@method_decorator(staff_member_required, name="dispatch")
class FlynoteManagerSearchView(FlynoteManagerMixin, TemplateView):
    template_name = "peachjam/flynote/manager/_search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()
        depth = self.request.GET.get("depth", "").strip()
        created_after = self.request.GET.get("created_after", "").strip()
        created_before = self.request.GET.get("created_before", "").strip()
        results = []
        path_labels = {}

        if query or depth or created_after or created_before:
            queryset = self.filter_deprecated_queryset(Flynote.objects.all())
            if query:
                queryset = queryset.filter(name__icontains=query)
            if depth:
                try:
                    queryset = queryset.filter(depth=int(depth))
                except ValueError:
                    depth = ""
            if created_after:
                date = parse_date(created_after)
                if date:
                    queryset = queryset.filter(created_at__date__gte=date)
                else:
                    created_after = ""
            if created_before:
                date = parse_date(created_before)
                if date:
                    queryset = queryset.filter(created_at__date__lte=date)
                else:
                    created_before = ""

            results = list(
                queryset.select_related("document_count_cache")
                .annotate(document_total=Coalesce("document_count_cache__count", 0))
                .order_by("-created_at", "name")[:100]
            )
            path_labels = self.get_flynote_path_labels(results)

        context["query"] = query
        context["depth"] = depth
        context["created_after"] = created_after
        context["created_before"] = created_before
        context["deprecated"] = "true" if self.deprecated_only() else "false"
        context["results"] = results
        context["path_labels"] = path_labels
        context["manager_url"] = reverse("flynote-manager")
        context["search_url"] = reverse("flynote-manager-search")
        max_depth = (
            Flynote.objects.order_by("-depth").values_list("depth", flat=True).first()
        )
        context["depth_choices"] = range(1, (max_depth or 1) + 1)
        return context


@method_decorator(staff_member_required, name="dispatch")
class FlynoteManagerDetailView(FlynoteManagerMixin, DetailView):
    template_name = "peachjam/flynote/manager/_detail.html"
    context_object_name = "flynote"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.GET.get("tab") == "merge" and request.user.has_perm(
            "peachjam.change_flynote"
        ):
            query = request.GET.get("q", self.object.name).strip()
            merge_context = self.get_merge_picker_context(
                request,
                self.object,
                query,
                self.get_merge_selected_ids(request.GET),
            )
            return self.detail_response(
                active_tab="merge",
                merge_context=merge_context,
            )
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_form(self):
        if self.request.method == "POST":
            return FlynoteManagerForm(self.request.POST, instance=self.object)
        return FlynoteManagerForm(instance=self.object)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ancestor_paths = [
            self.object.path[:end]
            for end in range(
                self.object.steplen,
                len(self.object.path),
                self.object.steplen,
            )
        ]
        context["ancestors"] = Flynote.objects.filter(path__in=ancestor_paths).order_by(
            "path"
        )
        try:
            context["document_count"] = self.object.document_count_cache.count
        except Flynote.document_count_cache.RelatedObjectDoesNotExist:
            context["document_count"] = 0
        context["form"] = kwargs.get("form") or self.get_form()
        context["can_change_flynote"] = self.request.user.has_perm(
            "peachjam.change_flynote"
        )
        context["can_delete_flynote"] = self.request.user.has_perm(
            "peachjam.delete_flynote"
        )
        context["manager_url"] = reverse("flynote-manager")
        context["app_label"] = self.object._meta.app_label
        context["model_name"] = self.object._meta.model_name
        context["log_entries"] = (
            LogEntry.objects.filter(
                content_type=self.get_flynote_content_type(),
                object_id=str(self.object.pk),
            )
            .select_related("user")
            .order_by("-action_time")[:20]
        )
        context["active_tab"] = kwargs.get("active_tab", "detail")
        if kwargs.get("merge_context"):
            context.update(kwargs["merge_context"])
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("_action", "save")

        if action == "delete":
            if not request.user.has_perm("peachjam.delete_flynote"):
                return HttpResponseForbidden("Forbidden")
            parent = self.object.get_parent()
            redirect_url = reverse("flynote-manager")
            if parent:
                redirect_url = f"{redirect_url}?flynote={parent.pk}"
            try:
                self.object.delete()
            except ProtectedError:
                return self.detail_response(
                    delete_error=(
                        "This flynote cannot be deleted because it or one of its descendants "
                        "has linked judgments."
                    )
                )

            response = HttpResponse(status=204)
            response["HX-Redirect"] = redirect_url
            return response

        if not request.user.has_perm("peachjam.change_flynote"):
            return HttpResponseForbidden("Forbidden")

        if action in ["deprecate", "undeprecate"]:
            was_deprecated = self.object.deprecated
            self.object.deprecated = action == "deprecate"
            self.object.save()
            if self.object.deprecated != was_deprecated:
                message = (
                    "Deprecated flynote."
                    if self.object.deprecated
                    else "Un-deprecated flynote."
                )
                self.log_flynote_change(request, self.object, message)
            return HttpResponseRedirect(
                reverse("flynote-manager-detail", args=[self.object.pk])
            )

        old_name = self.object.name
        form = self.get_form()
        saved = False
        if form.is_valid():
            form.save()
            self.object.refresh_from_db()
            if self.object.name != old_name:
                self.log_flynote_change(
                    request,
                    self.object,
                    f'Changed name from "{old_name}" to "{self.object.name}".',
                )
            saved = True

        return self.detail_response(form=form, saved=saved)

    def detail_response(
        self,
        form=None,
        saved=False,
        delete_error=None,
        active_tab="detail",
        merge_context=None,
    ):
        if form is None:
            form = FlynoteManagerForm(instance=self.object)
        response = self.render_to_response(
            self.get_context_data(
                form=form,
                saved=saved,
                delete_error=delete_error,
                active_tab=active_tab,
                merge_context=merge_context,
            )
        )
        if saved:
            response["HX-Trigger"] = json.dumps(
                {
                    "flynote-updated": {
                        "id": self.object.pk,
                        "name": self.object.name,
                        "deprecated": self.object.deprecated,
                    }
                }
            )
        return response


@method_decorator(staff_member_required, name="dispatch")
class FlynoteManagerMergeView(FlynoteManagerDetailView):
    template_name = "peachjam/flynote/manager/_merge.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("peachjam.change_flynote"):
            return HttpResponseForbidden("Forbidden")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        query = request.GET.get("q", self.object.name).strip()
        context = self.get_merge_picker_context(
            request,
            self.object,
            query,
            self.get_merge_selected_ids(request.GET),
        )
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        parent = self.object.get_parent()
        parent_id = parent.pk if parent else None
        selected_ids = self.get_merge_selected_ids(request.POST)
        selected_flynotes = list(
            Flynote.objects.filter(pk__in=selected_ids).order_by("name")
        )
        source_labels = [
            f"{flynote.name} ({flynote.pk})" for flynote in selected_flynotes
        ]
        merge_error = None
        merge_success = None

        try:
            self.object.merge_sources_into(selected_flynotes)
        except ValidationError as exc:
            merge_error = "; ".join(exc.messages)
        else:
            self.object.refresh_from_db()
            merge_success = (
                f"Merged {len(selected_ids)} flynotes into {self.object.name}."
            )
            if source_labels:
                self.log_flynote_change(
                    request,
                    self.object,
                    "Merged flynotes into this flynote: "
                    + ", ".join(source_labels)
                    + ".",
                )
            selected_ids = []

        query = request.POST.get("q", self.object.name).strip()
        merge_context = self.get_merge_picker_context(
            request,
            self.object,
            query,
            selected_ids,
        )
        merge_context["merge_error"] = merge_error
        merge_context["merge_success"] = merge_success

        self.template_name = "peachjam/flynote/manager/_detail.html"
        response = self.detail_response(
            active_tab="merge",
            merge_context=merge_context,
        )
        if merge_success:
            response["HX-Trigger"] = json.dumps(
                {
                    "flynote-merged": {
                        "targetId": self.object.pk,
                        "parentId": parent_id,
                    }
                }
            )
        return response


@method_decorator(staff_member_required, name="dispatch")
class FlynoteManagerMergePickerView(FlynoteManagerMixin, TemplateView):
    template_name = "peachjam/flynote/manager/_merge_picker_content.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("peachjam.change_flynote"):
            return HttpResponseForbidden("Forbidden")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        target = get_object_or_404(Flynote, pk=kwargs["pk"])
        selected_ids = self.get_merge_selected_ids(request.GET)
        query = request.GET.get("q", target.name).strip()

        add_id = request.GET.get("add")
        remove_id = request.GET.get("remove")
        if add_id:
            try:
                add_id = int(add_id)
            except (TypeError, ValueError):
                add_id = None
            if add_id and add_id not in selected_ids:
                selected_ids.append(add_id)
        if remove_id:
            try:
                remove_id = int(remove_id)
            except (TypeError, ValueError):
                remove_id = None
            if remove_id in selected_ids:
                selected_ids.remove(remove_id)

        context = self.get_merge_picker_context(request, target, query, selected_ids)
        return self.render_to_response(context)
