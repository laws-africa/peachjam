from lawlibrary.constants import PROVINCIAL_CODES
from liiweb.views import LegislationListView as BaseLegislationListView
from liiweb.views import LocalityLegislationView as BaseLocalityLegislationView
from peachjam.helpers import chunks
from peachjam.models import Locality


class LegislationListView(BaseLegislationListView):
    def get_queryset(self):
        return super().get_queryset().filter(locality=None)


class LocalityLegislationView(BaseLocalityLegislationView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        provincial_codes = PROVINCIAL_CODES
        localities = Locality.objects.filter(code__in=provincial_codes)
        context["locality_groups"] = list(chunks(localities, 2))
        context["locality_legislation_title"] = "Provincial Legislation"
        return context


class MunicipalLegislationView(BaseLocalityLegislationView):
    navbar_link = "legislation/municipal"
    template_name = "liiweb/locality_legislation.html"
    provincial_codes = PROVINCIAL_CODES

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["locality_legislation_title"] = "Municipal By-laws"
        municipalities = Locality.objects.exclude(code__in=self.provincial_codes)
        context["locality_groups"] = list(chunks(municipalities, 2))
        context["locality_legislation_title"] = "Municipal Legislation"
        return context
