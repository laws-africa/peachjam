from django.views.generic import TemplateView

from peachjam.models import CourtClass, CourtGroup, Judgment
from peachjam.registry import registry
from peachjam.views.generic_views import BaseDocumentDetailView


class JudgmentListView(TemplateView):
    model = Judgment
    template_name = "peachjam/judgment_list.html"
    navbar_link = "judgments"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["court_classes"] = CourtClass.objects.prefetch_related("courts")
        context["court_groups"] = CourtGroup.objects.prefetch_related("classes")
        context["recent_judgments"] = Judgment.objects.exclude(
            published=False
        ).order_by("-date")[:30]
        context["doc_type"] = "Judgment"
        return context


@registry.register_doc_type("judgment")
class JudgmentDetailView(BaseDocumentDetailView):
    model = Judgment
    template_name = "peachjam/judgment_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "judges": self.get_object()
                .bench.prefetch_related("judge")
                .values_list("judge__name", flat=True)
            }
        )
        return context
