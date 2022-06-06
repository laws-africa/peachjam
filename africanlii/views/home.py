from django.views.generic import TemplateView

from africanlii.models import (
    AuthoringBody,
    Court,
    GenericDocument,
    Judgment,
    LegalInstrument,
    Legislation,
)


class HomePageView(TemplateView):
    template_name = "africanlii/home.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        recent_judgments = Judgment.objects.order_by("-date")[:5]
        recent_documents = GenericDocument.objects.order_by("-date")[:5]
        recent_instruments = LegalInstrument.objects.order_by("-date")[:5]
        recent_legislation = Legislation.objects.order_by("-date")[:5]
        documents_count = GenericDocument.objects.count()
        courts = Court.objects.exclude(judgment__isnull=True).values("id", "name")
        authoring_bodies = AuthoringBody.objects.exclude(
            genericdocument__isnull=True, legalinstrument__isnull=True
        ).values("id", "name")

        context["recent_judgments"] = recent_judgments
        context["recent_documents"] = recent_documents
        context["recent_instruments"] = recent_instruments
        context["recent_legislation"] = recent_legislation
        context["documents_count"] = documents_count
        context["courts"] = courts
        context["authoring_bodies"] = authoring_bodies

        return self.render_to_response(context)
