from countries_plus.models import Country
from django.shortcuts import get_object_or_404

from peachjam.models import Locality
from peachjam.views import FilteredDocumentListView


class PlaceDetailView(FilteredDocumentListView):
    template_name = "peachjam/place_detail.html"

    def get(self, request, code, *args, **kwargs):
        if "-" in code:
            cty_code, locality_code = code.split("-", 1)
            self.country = get_object_or_404(Country.objects, pk=cty_code.upper())
            self.locality = get_object_or_404(
                Locality.objects, jurisdiction=self.country, code=locality_code
            )
        else:
            self.country = get_object_or_404(Country.objects, pk=code)
            self.locality = None

        self.place = self.locality or self.country
        return super().get(request, code, *args, **kwargs)

    def get_base_queryset(self):
        return (
            super()
            .get_base_queryset()
            .filter(jurisdiction=self.country, locality=self.locality)
        )

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            country=self.country, locality=self.locality, place=self.place, **kwargs
        )
