from django.views.generic import DetailView, ListView

from africanlii.models import Legislation
from peachjam.views import AuthedViewMixin


class LegislationListView(AuthedViewMixin, ListView):
    model = Legislation
    template_name = "africanlii/legislation_list.html"
    context_object_name = "legislation"
    paginate_by = 20


class LegislationDetailView(AuthedViewMixin, DetailView):
    model = Legislation
    template_name = "africanlii/legislation_detail.html"
    context_object_name = "document"
