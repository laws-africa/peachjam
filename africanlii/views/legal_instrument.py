from django.views.generic import DetailView, ListView

from africanlii.models import LegalInstrument
from peachjam.views import AuthedViewMixin


class LegalInstrumentListView(AuthedViewMixin, ListView):
    model = LegalInstrument
    template_name = "africanlii/legal_instrument_list.html"
    context_object_name = "documents"
    paginate_by = 20


class LegalInstrumentDetailView(AuthedViewMixin, DetailView):
    model = LegalInstrument
    template_name = "africanlii/legal_instrument_detail.html"
    context_object_name = "document"
