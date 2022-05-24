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


class AuthorListView(AuthedViewMixin, ListView):
    template_name = "africanlii/author_detail.html"
    context_object_name = "documents"
    paginate_by = 20

    def get_queryset(self):

        try:
            court = Court.objects.get(
                pk=self.kwargs["pk"], name=self.kwargs["author_name"]
            )
            documents = Judgment.objects.filter(court=court)
        except Court.DoesNotExist:
            authoring_body = AuthoringBody.objects.get(
                pk=self.kwargs["pk"], name=self.kwargs["author_name"]
            )
            generic_documents = GenericDocument.objects.filter(
                authoring_body=authoring_body
            )
            legal_instruments = LegalInstrument.objects.filter(
                authoring_body=authoring_body
            )
            documents = list(chain(generic_documents, legal_instruments))

        return documents

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.kwargs["author_name"]
        return context
