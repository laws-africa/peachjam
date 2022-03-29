from django.views.generic import ListView, DetailView

from africanlii.models import Legislation
from peachjam.views import AuthedViewMixin

class LegislationListView(AuthedViewMixin, ListView):
    template_name = 'africanlii/legislation_list.html'
    context_object_name = 'legislation'
    paginate_by = 20
    

    def get_queryset(self):
        return Legislation.objects.all()


class LegislationDetailView(AuthedViewMixin, DetailView):
    model = Legislation
    template_name = 'africanlii/legislation_detail.html'
    context_object_name = 'legislation'
