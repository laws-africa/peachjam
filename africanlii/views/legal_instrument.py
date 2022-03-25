from django.views.generic import ListView, DetailView

from africanlii.models import LegalInstrument
from peachjam.views import AuthedViewMixin


class LegalInstrumentListView(AuthedViewMixin, ListView):
    template_name = 'africanlii/legal_instrument_list.html'
    context_object_name = 'legal_instruments'

    def get_queryset(self):
        return LegalInstrument.objects.all()


class LegalInstrumentDetailView(AuthedViewMixin, DetailView):
    model = LegalInstrument
    template_name = 'africanlii/legal_instrument_detail.html'
    context_object_name = 'legal_instrument'
