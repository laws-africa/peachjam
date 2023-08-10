from liiweb.views.legislation import LocalityLegislationListView


class MunicipalByLawsView(LocalityLegislationListView):
    template_name = "open_by_laws/municipal_by_laws_list.html"
