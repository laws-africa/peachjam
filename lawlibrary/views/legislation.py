from liiweb.views import LegislationListView as BaseLegislationListView
from liiweb.views import LocalityLegislationListView as BaseLocalityLegislationListView
from liiweb.views import LocalityLegislationView as BaseLocalityLegislationView
from peachjam.models import Locality


class LegislationListView(BaseLegislationListView):
    def get_queryset(self):
        return super().get_queryset().filter(locality=None)


class LocalityLegislationView(BaseLocalityLegislationView):
    navbar_link = "legislation/provincial"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        codes = "mp ec nc kzn gp wc lp nw fs".split()
        provinces = Locality.objects.filter(code__in=codes)
        context["province_groups"] = provinces[:5], provinces[5:]
        context["page_heading"] = "Provincial Legislation"
        return context


class LocalityLegislationListView(BaseLocalityLegislationListView):
    navbar_link = "legislation/provincial"
