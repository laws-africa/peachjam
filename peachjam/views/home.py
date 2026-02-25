from django.db.models import Q
from django.views.generic import TemplateView

from peachjam.models import Author, GenericDocument, Judgment, Legislation
from peachjam.models.settings import pj_settings


class HomePageView(TemplateView):
    template_name = "peachjam/home.html"
    navbar_link = "home"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        recent_judgments = (
            Judgment.objects.exclude(published=False)
            .for_document_table()
            .order_by("-date")[:5]
        )
        recent_documents = (
            GenericDocument.objects.exclude(published=False)
            .for_document_table()
            .order_by("-date")[:5]
        )
        recent_legislation = (
            Legislation.objects.exclude(published=False)
            .for_document_table()
            .order_by("-date")[:5]
        )

        authors = Author.objects.exclude(
            Q(genericdocument__isnull=True),
        )

        context["recent_judgments"] = recent_judgments
        context["recent_documents"] = recent_documents
        context["recent_legislation"] = recent_legislation
        context["authors"] = authors
        context["has_flynote_topics"] = bool(pj_settings().flynote_taxonomy_root)

        return context
