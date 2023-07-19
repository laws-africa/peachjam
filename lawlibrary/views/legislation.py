from liiweb.views import LegislationListView as BaseLegislationListView
from liiweb.views import LocalityLegislationView as BaseLocalityLegislationView


class LegislationListView(BaseLegislationListView):
    def get_queryset(self):
        return super().get_queryset().filter(locality=None)


class LocalityLegislationView(BaseLocalityLegislationView):
    def get_context_data(self, **kwargs):
        return super().get_context_data(
            locality_legislation_title="Provincial Legislation", **kwargs
        )
