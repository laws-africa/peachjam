from peachjam.models.core_document import get_country_and_locality_or_404
from peachjam.views import FilteredDocumentListView


class PlaceDetailView(FilteredDocumentListView):
    template_name = "peachjam/place_detail.html"

    def get(self, request, code, *args, **kwargs):
        self.country, self.locality = get_country_and_locality_or_404(code)
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
