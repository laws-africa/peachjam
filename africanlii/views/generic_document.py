from django.views.generic import DetailView, ListView

from africanlii.models import GenericDocument
from peachjam.views import AuthedViewMixin


class GenericDocumentListView(AuthedViewMixin, ListView):
    template_name = "africanlii/generic_document_list.html"
    context_object_name = "documents"
    paginate_by = 20
    model = GenericDocument


class GenericDocumentDetailView(AuthedViewMixin, DetailView):
    model = GenericDocument
    template_name = "africanlii/generic_document_detail.html"
    context_object_name = "document"
