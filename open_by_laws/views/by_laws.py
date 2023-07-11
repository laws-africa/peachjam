from lawlibrary.views.legislation import ProvincialLegislationListView


class MunicipalByLawsView(ProvincialLegislationListView):
    template_name = "open_by_laws/municipal_by_laws_list.html"
