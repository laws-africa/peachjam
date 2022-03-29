from django.views.generic import ListView, DetailView
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from africanlii.models import GenericDocument
from peachjam.views import AuthedViewMixin


class GenericDocumentListView(AuthedViewMixin, ListView):
    template_name = 'africanlii/generic_document_list.html'
    context_object_name = 'generic_documents'
    paginate_by = 20

    def get_queryset(self):
        return GenericDocument.objects.all()
    
    

class GenericDocumentDetailView(AuthedViewMixin, DetailView):
    model = GenericDocument
    template_name = 'africanlii/generic_document_detail.html'
    context_object_name = 'generic_document'
