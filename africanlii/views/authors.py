from itertools import chain

from django.views.generic import ListView

from africanlii.models import (
    AuthoringBody,
    Court,
    GenericDocument,
    Judgment,
    LegalInstrument,
)
from peachjam.views import AuthedViewMixin


class BaseAuthorListView(AuthedViewMixin, ListView):
    context_object_name = "documents"
    paginate_by = 20


class CourtListView(BaseAuthorListView):
    template_name = "africanlii/_court_detail.html"
    model = Court

    def get_queryset(self):
        court = self.model.objects.get(pk=self.kwargs["pk"])
        return Judgment.objects.filter(court=court)

    def get_context_data(self, **kwargs):
        context = super(CourtListView, self).get_context_data(**kwargs)
        author = self.model.objects.get(pk=self.kwargs["pk"])
        context["author"] = author
        return context


class AuthoringBodyListView(BaseAuthorListView):
    template_name = "africanlii/_author_detail.html"
    model = AuthoringBody

    def get_queryset(self):
        authoring_body = self.model.objects.get(pk=self.kwargs["pk"])
        generic_documents = GenericDocument.objects.filter(
            authoring_body=authoring_body
        )
        legal_instruments = LegalInstrument.objects.filter(
            authoring_body=authoring_body
        )
        return list(chain(generic_documents, legal_instruments))

    def get_context_data(self, **kwargs):
        context = super(AuthoringBodyListView, self).get_context_data(**kwargs)
        author = self.model.objects.get(pk=self.kwargs["pk"])
        context["author"] = author
        return context
