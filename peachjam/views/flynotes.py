import json

from django import forms
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseForbidden, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import DetailView, TemplateView

from peachjam.models.flynote import Flynote


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


class FlynoteManagerMixin:
    model = Flynote

    def get_queryset(self):
        return self.model.objects.select_related("document_count_cache")

    def serialize_node(self, flynote):
        try:
            document_count = flynote.document_count_cache.count
        except Flynote.document_count_cache.RelatedObjectDoesNotExist:
            document_count = 0

        return {
            "id": flynote.pk,
            "name": flynote.name,
            "deprecated": flynote.deprecated,
            "numchild": flynote.numchild,
            "document_count": document_count,
            "has_children": flynote.numchild > 0,
        }


@method_decorator(staff_member_required, name="dispatch")
class FlynoteManagerTreeView(FlynoteManagerMixin, View):
    def get(self, request, *args, **kwargs):
        flynotes = Flynote.get_root_nodes().select_related("document_count_cache")
        return JsonResponse({"results": [self.serialize_node(f) for f in flynotes]})


@method_decorator(staff_member_required, name="dispatch")
class FlynoteManagerTreeChildrenView(FlynoteManagerMixin, View):
    def get(self, request, *args, **kwargs):
        parent = get_object_or_404(Flynote, pk=kwargs["pk"])
        flynotes = parent.get_children().select_related("document_count_cache")
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
class FlynoteManagerSearchView(TemplateView):
    template_name = "peachjam/flynote/manager/_search.html"


@method_decorator(staff_member_required, name="dispatch")
class FlynoteManagerDetailView(FlynoteManagerMixin, DetailView):
    template_name = "peachjam/flynote/manager/_detail.html"
    context_object_name = "flynote"

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
        context["manager_url"] = reverse("flynote-manager")
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.has_perm("peachjam.change_flynote"):
            return HttpResponseForbidden("Forbidden")

        self.object = self.get_object()
        action = request.POST.get("_action", "save")
        if action in ["deprecate", "undeprecate"]:
            self.object.deprecated = action == "deprecate"
            self.object.save()
            return HttpResponseRedirect(
                reverse("flynote-manager-detail", args=[self.object.pk])
            )

        form = self.get_form()
        saved = False
        if form.is_valid():
            form.save()
            self.object.refresh_from_db()
            saved = True

        return self.detail_response(form=form, saved=saved)

    def detail_response(self, form=None, saved=False):
        response = self.render_to_response(
            self.get_context_data(form=form, saved=saved)
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
