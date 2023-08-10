from liiweb.views import LegislationListView as BaseLegislationListView
from liiweb.views import LocalityLegislationView as BaseLocalityLegislationView
from peachjam.helpers import chunks
from peachjam.models import Locality


class LegislationListView(BaseLegislationListView):
    def get_queryset(self):
        return super().get_queryset().filter(locality=None)


class LocalityLegislationView(BaseLocalityLegislationView):
    def get_context_data(self, **kwargs):
        return super().get_context_data(
            locality_legislation_title="Provincial Legislation", **kwargs
        )


class MunicipalLegislationView(BaseLocalityLegislationView):
    navbar_link = "legislation/municipal"
    template_name = "liiweb/municipal_legislation.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["locality_legislation_title"] = "Municipal By-laws"
        codes = "cpt eth jhb wc015 wc041 wc023 wc013 wc033 wc012 ec443 wc011".split()
        municipalities = Locality.objects.filter(code__in=codes)
        context["municipality_groups"] = list(chunks(municipalities, 2))
        return context
