from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.generic import ListView

from africanlii.forms import BaseDocumentFilterForm
from africanlii.utils import lowercase_alphabet
from peachjam.models import Author, CoreDocument


def add_facet_data_to_context(years, doc_types):
    return {"years": years, "doc_types": doc_types, "alphabet": lowercase_alphabet()}


class BaseAuthorListView(ListView):
    context_object_name = "documents"
    paginate_by = 20
    model = Author
    template_name = "africanlii/_author_detail.html"


class AuthorListView(BaseAuthorListView):
    def get_queryset(self):
        self.form = BaseDocumentFilterForm(self.request.GET)
        self.form.is_valid()
        author = get_object_or_404(self.model, pk=self.kwargs["pk"])

        queryset = CoreDocument.objects.filter(
            Q(genericdocument__author=author)
            | Q(legalinstrument__author=author)
            | Q(judgment__author=author)
        )

        return self.form.filter_queryset(queryset)

    def get_context_data(self, **kwargs):
        context = super(AuthorListView, self).get_context_data(**kwargs)
        author = get_object_or_404(self.model, pk=self.kwargs["pk"])

        generic_doc_years = []
        generic_document_doc_type = []
        generic_docs = author.genericdocument_set.all()
        if generic_docs.exists():
            generic_doc_years = generic_docs.values_list("date__year", flat=True)
            generic_document_doc_type = generic_docs.values_list("doc_type", flat=True)

        legal_instrument_years = []
        legal_instrument_doc_type = []
        legal_instruments = author.legalinstrument_set.all()
        if legal_instruments.exists():
            legal_instrument_years = legal_instruments.values_list(
                "date__year", flat=True
            )
            legal_instrument_doc_type = legal_instruments.values_list(
                "doc_type", flat=True
            )

        judgment_years = []
        judgment_doc_type = []
        judgments = author.judgment_set.all()
        if judgments.exists():
            judgment_years = judgments.values_list("date__year", flat=True)
            judgment_doc_type = judgments.values_list("doc_type", flat=True)

        years = list(
            set(
                list(generic_doc_years)
                + list(legal_instrument_years)
                + list(judgment_years)
            )
        )

        doc_types = (
            list(generic_document_doc_type)
            + list(legal_instrument_doc_type)
            + list(judgment_doc_type)
        )

        context["author"] = author
        context["facet_data"] = add_facet_data_to_context(years, doc_types)

        return context
