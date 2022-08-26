from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from peachjam.models import Legislation, Locality
from peachjam_api.serializers import LegislationSerializer


class LegislationListView(TemplateView):
    template_name = "lawlibrary/legislation_list.html"
    variant = None

    def get_queryset(self):
        return (
            Legislation.objects.filter(locality=None)
            .distinct("work_frbr_uri")
            .order_by("work_frbr_uri", "-date")
        )

    def filter_queryset(self, qs):
        if self.variant == "all":
            pass
        elif self.variant == "repealed":
            qs = qs.filter(repealed=True)
        else:
            qs = qs.filter(metadata_json__stub=False)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = self.filter_queryset(self.get_queryset())
        context["legislation_table"] = LegislationSerializer(qs, many=True).data
        context["provinces"] = Locality.objects.filter(jurisdiction__iso="ZA")

        return context


class ProvincialLegislationListView(LegislationListView):
    model = Legislation
    template_name = "lawlibrary/provincial_legislation_list.html"

    def get(self, *args, **kwargs):
        self.locality = get_object_or_404(Locality, code=kwargs["code"])
        return super().get(*args, **kwargs)

    def get_queryset(self):
        return (
            Legislation.objects.filter(locality=self.locality)
            .distinct("work_frbr_uri")
            .order_by("work_frbr_uri", "-date")
        )

    def get_context_data(self, **kwargs):
        return super().get_context_data(locality=self.locality, **kwargs)
