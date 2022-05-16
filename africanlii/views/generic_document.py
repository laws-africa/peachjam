from django.views.generic import DetailView, ListView

from africanlii.models import GenericDocument
from africanlii.registry import registry
from peachjam.views import AuthedViewMixin


class GenericDocumentListView(AuthedViewMixin, ListView):
    template_name = "africanlii/generic_document_list.html"
    context_object_name = "documents"
    paginate_by = 20
    model = GenericDocument

    def get_queryset(self):
        self.form = DocumentFilterForm(self.request.GET)
        self.form.is_valid()
        queryset = GenericDocument.objects.all()
        return self.form.filter_queryset(queryset)

    def get_context_data(self, **kwargs):
        context = super(GenericDocumentListView, self).get_context_data(**kwargs)
        authors = list(
            set(GenericDocument.objects.values_list("authoring_body__name", flat=True))
        )
        context["authors"] = authors
        return context


@registry.register_doc_type("generic_document")
class GenericDocumentDetailView(AuthedViewMixin, DetailView):
    model = GenericDocument
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "expression_frbr_uri"
    template_name = "africanlii/generic_document_detail.html"
    context_object_name = "document"
