from itertools import chain

from django.views.generic import TemplateView

from africanlii.models import (
    AuthoringBody,
    Court,
    GenericDocument,
    Judgment,
    LegalInstrument,
    Legislation,
)
from peachjam.views import AuthedViewMixin


class HomePageView(AuthedViewMixin, TemplateView):
    template_name = "africanlii/home.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        recent_judgments = Judgment.objects.order_by("-date")[:5]
        recent_documents = GenericDocument.objects.order_by("-date")[:5]
        recent_instruments = LegalInstrument.objects.order_by("-date")[:5]
        recent_legislation = Legislation.objects.order_by("-date")[:5]
        documents_count = GenericDocument.objects.count()

        # Judgments have courts as their authors. Querying the Courts should suffice.
        judgments_authors = Court.objects.values("id", "name", "slug")

        # CoreDocuments have the AuthoringBody as the author. Querying the AuthoringBody model should suffice
        core_documents_authors = AuthoringBody.objects.values("id", "name", "slug")
        authors = list(chain(judgments_authors, core_documents_authors))

        context["recent_judgments"] = recent_judgments
        context["recent_documents"] = recent_documents
        context["recent_instruments"] = recent_instruments
        context["recent_legislation"] = recent_legislation
        context["documents_count"] = documents_count
        context["authors"] = authors

        return self.render_to_response(context)
