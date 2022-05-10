from django.views.generic import TemplateView

from africanlii.models import GenericDocument, Judgment, LegalInstrument, Legislation
from peachjam.views import AuthedViewMixin


class HomePageView(AuthedViewMixin, TemplateView):
    template_name = "africanlii/home.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        recent_judgments = Judgment.objects.filter().order_by("-created_at")[:5]
        context["recent_judgments"] = recent_judgments
        recent_documents = GenericDocument.objects.filter().order_by("-created_at")[:5]
        context["recent_documents"] = recent_documents
        recent_legislation = Legislation.objects.filter().order_by("-created_at")[:5]
        context["recent_legislation"] = recent_legislation
        recent_instruments = LegalInstrument.objects.filter().order_by("-created_at")[
            :5
        ]
        context["recent_instruments"] = recent_instruments
        return self.render_to_response(context)
