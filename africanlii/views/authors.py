from itertools import chain

from django.shortcuts import get_object_or_404
from django.views.generic import ListView

from africanlii.forms import BaseDocumentFilterForm
from africanlii.models import Author, Judgment
from africanlii.utils import lowercase_alphabet
from peachjam.models import CoreDocument
from peachjam.models.generic_document import GenericDocument, LegalInstrument


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

        if CoreDocument.objects.filter(genericdocument__author=author).exists():
            queryset = GenericDocument.objects.filter(author=author)

        if CoreDocument.objects.filter(legalinstrument__author=author).exists():
            queryset = LegalInstrument.objects.filter(author=author)

        if CoreDocument.objects.filter(judgment__author=author).exists():
            queryset = Judgment.objects.filter(author=author)

        return self.form.filter_queryset(queryset)

    def get_context_data(self, **kwargs):
        context = super(AuthorListView, self).get_context_data(**kwargs)
        author = get_object_or_404(self.model, pk=self.kwargs["pk"])

        # Filter doc years to be used in listing facets
        generic_doc_years = author.genericdocument_set.values_list(
            "date__year", flat=True
        )
        legal_instrument_years = author.legalinstrument_set.values_list(
            "date__year", flat=True
        )
        judgment_years = author.judgment_set.values_list("date__year", flat=True)
        years = list(
            set((chain(generic_doc_years, legal_instrument_years, judgment_years)))
        )

        # Filter doc_types to be used in listing facets
        generic_document_doc_type = author.genericdocument_set.values_list(
            "doc_type", flat=True
        )
        legal_instrument_doc_type = author.legalinstrument_set.values_list(
            "doc_type", flat=True
        )
        judgment_doc_type = author.judgment_set.values_list("doc_type", flat=True)
        doc_types = list(
            set(
                chain(
                    generic_document_doc_type,
                    legal_instrument_doc_type,
                    judgment_doc_type,
                )
            )
        )

        context["author"] = author
        context["facet_data"] = add_facet_data_to_context(years, doc_types)

        return context
