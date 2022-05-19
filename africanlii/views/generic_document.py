from django.views.generic import DetailView

from africanlii.forms import BaseDocumentFilterForm
from africanlii.models import GenericDocument
from africanlii.registry import registry
from africanlii.views.generic_views import FilteredDocumentListView
from peachjam.views import AuthedViewMixin


class GenericDocumentListView(AuthedViewMixin, FilteredDocumentListView):
    template_name = "africanlii/generic_document_list.html"
    context_object_name = "documents"
    paginate_by = 20
    model = GenericDocument

    def __init__(self, *args, **kwargs):
        super(BaseDocumentFilterForm, self).__init__(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(FilteredDocumentListView, self).get_context_data(**kwargs)
        years = (
            GenericDocument.objects.values_list("date__year", flat=True)
            .order_by()
            .distinct()
        )
        context["years"] = years
        return context


@registry.register_doc_type("generic_document")
class GenericDocumentDetailView(AuthedViewMixin, DetailView):
    model = GenericDocument
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "expression_frbr_uri"
    template_name = "africanlii/generic_document_detail.html"
    context_object_name = "document"
