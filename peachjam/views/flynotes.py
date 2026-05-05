from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import DetailView, TemplateView

from peachjam.models.flynote import Flynote


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
class FlynoteManagerSearchView(TemplateView):
    template_name = "peachjam/flynote/manager/_search.html"


@method_decorator(staff_member_required, name="dispatch")
class FlynoteManagerDetailView(FlynoteManagerMixin, DetailView):
    template_name = "peachjam/flynote/manager/_detail.html"
    context_object_name = "flynote"

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
        return context
