from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from liiweb.views.legislation import LegislationListView as BaseLegislationListView
from peachjam.models import Locality


class LegislationListView(BaseLegislationListView):
    def get_queryset(self):
        return super().get_queryset().filter(locality=None)


class ProvincialLegislationView(TemplateView):
    template_name = "lawlibrary/provincial_legislation.html"
    navbar_link = "legislation/provincial"

    def get_context_data(self, **kwargs):
        codes = "mp ec nc kzn gp wc lp nw fs".split()
        provinces = Locality.objects.filter(code__in=codes)
        groups = provinces[:5], provinces[5:]
        return super().get_context_data(province_groups=groups, **kwargs)


class ProvincialLegislationListView(BaseLegislationListView):
    template_name = "lawlibrary/provincial_legislation_list.html"
    navbar_link = "legislation/provincial"

    def get(self, *args, **kwargs):
        self.locality = get_object_or_404(Locality, code=kwargs["code"])
        return super().get(*args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(locality=self.locality)

    def get_context_data(self, **kwargs):
        return super().get_context_data(locality=self.locality, **kwargs)
