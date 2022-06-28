from itertools import chain

from django.shortcuts import get_object_or_404
from django.views.generic import ListView

from africanlii.forms import BaseDocumentFilterForm
from africanlii.models import Author
from africanlii.utils import lowercase_alphabet
from peachjam.models import CoreDocument


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

        queryset = (
            CoreDocument.objects.filter(genericdocument__author=author)
            | CoreDocument.objects.filter(legalinstrument__author=author)
            | CoreDocument.objects.filter(judgment__author=author)
        )

        return self.form.filter_queryset(queryset)

    def get_context_data(self, **kwargs):
        context = super(AuthorListView, self).get_context_data(**kwargs)
        court = get_object_or_404(self.model, pk=self.kwargs["pk"])
        years = list(set(court.judgment_set.values_list("date__year", flat=True)))
        doc_types = list(set(court.judgment_set.values_list("doc_type", flat=True)))

        context["author"] = court
        context["facet_data"] = add_facet_data_to_context(years, doc_types)

        return context


class AuthoringBodyListView(BaseAuthorListView):
    template_name = "africanlii/_author_detail.html"

    def get_queryset(self):
        self.form = BaseDocumentFilterForm(self.request.GET)
        self.form.is_valid()
        authoring_body = get_object_or_404(self.model, pk=self.kwargs["pk"])

        queryset = CoreDocument.objects.filter(
            genericdocument__authoring_body=authoring_body
        ) | CoreDocument.objects.filter(legalinstrument__authoring_body=authoring_body)

        return self.form.filter_queryset(queryset)

    def get_context_data(self, **kwargs):
        context = super(AuthoringBodyListView, self).get_context_data(**kwargs)
        authoring_body = get_object_or_404(self.model, pk=self.kwargs["pk"])

        generic_doc_years = authoring_body.genericdocument_set.values_list(
            "date__year", flat=True
        )
        legal_instrument_years = authoring_body.legalinstrument_set.values_list(
            "date__year", flat=True
        )
        years = list(set((chain(generic_doc_years, legal_instrument_years))))

        generic_document_doc_type = authoring_body.genericdocument_set.values_list(
            "doc_type", flat=True
        )
        legal_instrument_doc_type = authoring_body.legalinstrument_set.values_list(
            "doc_type", flat=True
        )
        doc_types = list(
            set(chain(generic_document_doc_type, legal_instrument_doc_type))
        )

        context["author"] = authoring_body
        context["facet_data"] = add_facet_data_to_context(years, doc_types)

        return context
