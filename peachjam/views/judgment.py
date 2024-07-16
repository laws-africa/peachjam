from django.views.generic import TemplateView

from peachjam.models import CourtClass, Judgment
from peachjam.registry import registry
from peachjam.views.generic_views import BaseDocumentDetailView


class JudgmentListView(TemplateView):
    model = Judgment
    template_name = "peachjam/judgment_list.html"
    navbar_link = "judgments"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["court_classes"] = CourtClass.objects.prefetch_related("courts")
        context["recent_judgments"] = Judgment.objects.exclude(
            published=False
        ).order_by("-date")[:30]
        context["doc_type"] = "Judgment"
        context["doc_count"] = Judgment.objects.filter(published=True).count()
        context["help_link"] = "judgments/courts"
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
                .values_list("judge__name", flat=True),
                "case_histories": self.get_object()
                .work.case_histories.select_related(
                    "court", "historical_judgment_work", "outcome"
                )
                .prefetch_related(
                    "judges",
                    "historical_judgment_work__documents",
                    "historical_judgment_work__documents__outcomes",
                    "historical_judgment_work__documents__court",
                    "historical_judgment_work__documents__judges",
                ),
            }
        )
        return context
