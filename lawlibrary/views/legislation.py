from django.views.generic import ListView

from peachjam.models import Legislation, Locality
from peachjam_api.serializers import LegislationSerializer


class LegislationListView(ListView):
    model = Legislation
    template_name = "lawlibrary/legislation_list.html"
    context_object_name = "documents"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = (
            self.get_queryset()
            .filter(locality=None)
            .distinct("work_frbr_uri")
            .order_by("work_frbr_uri", "-date")
        )
        context["national_legislation_list"] = LegislationSerializer(qs, many=True).data

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
        context["facet_data"] = {"years": self.get_years()}

        return context

    def get_jurisdictions(self):
        return (
            self.get_queryset()
            .order_by("jurisdiction__name")
            .values_list("jurisdiction__name", flat=True)
            .distinct()
        )

    def get_queryset(self):
        return super().get_queryset()

    def get_years(self):
        qs = (
            self.get_queryset()
            .filter(locality=None)
            .order_by()
            .values_list("date__year", flat=True)
            .distinct()
        )
        return sorted(qs, reverse=True)

    # TODO: fetch taxonomies
    def get_taxonomies(self):
        pass


class ProvincialLegislationListView(ListView):
    model = Legislation
    template_name = "lawlibrary/provincial_legislation_list.html"
    context_object_name = "documents"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = (
            self.get_queryset()
            .filter(locality__code=self.kwargs["code"])
            .distinct("work_frbr_uri")
            .order_by("work_frbr_uri", "-date")
        )

        context["legislation_table"] = LegislationSerializer(qs, many=True).data
        context["facet_data"] = {"years": self.get_years()}

        return context

    def get_queryset(self):
        return super().get_queryset()

    def get_years(self):
        qs = (
            self.get_queryset()
            .filter(locality__code=self.kwargs["code"])
            .order_by()
            .values_list("date__year", flat=True)
            .distinct()
        )
        return sorted(qs, reverse=True)
