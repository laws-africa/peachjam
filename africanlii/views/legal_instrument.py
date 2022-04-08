from django.views.generic import ListView, DetailView
from africanlii.models import LegalInstrument
from peachjam.views import AuthedViewMixin


class LegalInstrumentListView(AuthedViewMixin, ListView):
    model = LegalInstrument
    template_name = 'africanlii/legal_instrument_list.html'
    context_object_name = 'legal_instruments'
    paginate_by = 20


class LegalInstrumentDetailView(AuthedViewMixin, DetailView):
    model = LegalInstrument
    template_name = 'africanlii/legal_instrument_detail.html'
    context_object_name = 'legal_instrument'
