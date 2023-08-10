from django.shortcuts import get_object_or_404

from liiweb.views.legislation import LocalityLegislationListView
from peachjam.models import Locality


class MunicipalByLawsView(LocalityLegislationListView):
    template_name = "open_by_laws/municipal_by_laws_list.html"
    navbar_link = "legislation/municipal"

    def get(self, *args, **kwargs):
        self.municipality = get_object_or_404(Locality, code=kwargs["code"])
        return super().get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        return super().get_context_data(municipality=self.municipality, **kwargs)
