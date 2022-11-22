from django.shortcuts import get_object_or_404

from peachjam.models import Locality
from peachjam.views import GazetteListView, GazetteYearView


class LawLibraryGazetteListView(GazetteListView):
    def get(self, request, code=None, *args, **kwargs):
        self.locality = get_object_or_404(Locality, code=code) if code else None
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(locality=self.locality)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(locality=self.locality, **kwargs)

        provinces = list(Locality.objects.all())
        context["province_groups"] = provinces[:5], provinces[5:]

        return context


class LawLibraryGazetteYearView(GazetteYearView):
    def get(self, request, code=None, *args, **kwargs):
        self.locality = get_object_or_404(Locality, code=code) if code else None
        return super().get(request, *args, **kwargs)

    def get_base_queryset(self):
        return super().get_base_queryset().filter(locality=self.locality)

    def get_context_data(self, **kwargs):
        return super().get_context_data(locality=self.locality, **kwargs)
