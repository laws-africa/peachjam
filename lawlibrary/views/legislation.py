from django.views.generic import TemplateView

from peachjam.models import Legislation, Locality
from peachjam_api.serializers import LegislationSerializer


class LegislationListView(TemplateView):
    template_name = "lawlibrary/legislation_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = (
            Legislation.objects.filter(locality=None, metadata_json__stub=False)
            .distinct("work_frbr_uri")
            .order_by("work_frbr_uri", "-date")
        )
        context["national_legislation_list"] = LegislationSerializer(qs, many=True).data
        context["provinces"] = Locality.objects.filter(jurisdiction__iso="ZA")

        return context


class ProvincialLegislationListView(TemplateView):
    model = Legislation
    template_name = "lawlibrary/provincial_legislation_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["locality"] = locality = Locality.objects.get(code=self.kwargs["code"])
        qs = (
            Legislation.objects.filter(locality=locality, metadata_json__stub=False)
            .distinct("work_frbr_uri")
            .order_by("work_frbr_uri", "-date")
        )
        context["legislation_table"] = LegislationSerializer(qs, many=True).data

        return context
