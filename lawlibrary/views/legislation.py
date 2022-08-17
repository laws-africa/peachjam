from django.views.generic import ListView

from peachjam.models import Legislation, Locality
from peachjam_api.serializers import LegislationSerializer


class LegislationListView(ListView):
    model = Legislation
    template_name = "lawlibrary/legislation_list.html"
    context_object_name = "documents"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["national_legislation_list"] = LegislationSerializer(
            self.model.objects.filter(locality=None), many=True
        ).data

        provincial_legislation_list = []

        for jurisdiction in self.get_jurisdictions():
            country_dict = {
                "localities": [
                    {
                        "code": locality.code,
                        "name": locality.name,
                    }
                    for locality in Locality.objects.filter(
                        jurisdiction__name=jurisdiction
                    )
                ],
            }
            provincial_legislation_list.append(country_dict)

        context["provincial_legislation_list"] = provincial_legislation_list

        return context

    def get_jurisdictions(self):
        return (
            self.model.objects.order_by("jurisdiction__name")
            .values_list("jurisdiction__name", flat=True)
            .distinct()
        )


class ProvincialLegislationListView(ListView):
    model = Legislation
    template_name = "lawlibrary/provincial_legislation_list.html"
    context_object_name = "documents"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["legislation_table"] = LegislationSerializer(
            self.model.objects.filter(locality__code=self.kwargs["code"]), many=True
        ).data
        return context
