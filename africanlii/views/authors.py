from itertools import chain

from django.shortcuts import get_object_or_404
from django.views.generic import ListView

from africanlii.forms import BaseDocumentFilterForm
from africanlii.models import AuthoringBody, Court
from peachjam.models import CoreDocument


def add_facet_data_to_context(years):
    return {
        "years": years,
        "alphabet": [
            "a",
            "b",
            "c",
            "d",
            "e",
            "f",
            "g",
            "h",
            "i",
            "j",
            "k",
            "l",
            "m",
            "n",
            "o",
            "p",
            "q",
            "r",
            "s",
            "t",
            "u",
            "v",
            "w",
            "x",
            "y",
            "z",
        ],
    }


class BaseAuthorListView(ListView):
    context_object_name = "documents"
    paginate_by = 20


class CourtListView(BaseAuthorListView):
    template_name = "africanlii/_court_detail.html"
    model = Court

    def get_queryset(self):
        self.form = BaseDocumentFilterForm(self.request.GET)
        self.form.is_valid()
        court = get_object_or_404(self.model, pk=self.kwargs["pk"])
        queryset = court.judgment_set.all()
        return self.form.filter_queryset(queryset)

    def get_context_data(self, **kwargs):
        context = super(CourtListView, self).get_context_data(**kwargs)
        court = get_object_or_404(self.model, pk=self.kwargs["pk"])
        years = list(set(court.judgment_set.values_list("date__year", flat=True)))

        context["author"] = court
        context["facet_data"] = add_facet_data_to_context(years)
        return context


class AuthoringBodyListView(BaseAuthorListView):
    template_name = "africanlii/_author_detail.html"
    model = AuthoringBody

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

        context["author"] = authoring_body
        context["facet_data"] = add_facet_data_to_context(years)
        return context
