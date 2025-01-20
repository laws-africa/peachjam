from django.contrib import messages
from django.utils.safestring import mark_safe
from django.utils.text import gettext_lazy as _
from django.utils.timezone import now
from django.views.generic import TemplateView

from peachjam.models import CourtClass, Judgment
from peachjam.registry import registry
from peachjam.views.generic_views import BaseDocumentDetailView


class JudgmentListView(TemplateView):
    template_name = "peachjam/judgment_list.html"
    navbar_link = "judgments"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["recent_judgments"] = (
            Judgment.objects.select_related("work")
            .prefetch_related("labels")
            .exclude(published=False)
            .order_by("-date")[:30]
        )
        context["nature"] = "Judgment"
        context["doc_count"] = Judgment.objects.filter(published=True).count()
        context["doc_count_noun"] = _("judgment")
        context["doc_count_noun_plural"] = _("judgments")
        context["help_link"] = "judgments/courts"
        self.add_entity_profile(context)
        self.get_court_classes(context)
        return context

    def get_court_classes(self, context):
        context["court_classes"] = CourtClass.objects.prefetch_related("courts")

    def add_entity_profile(self, context):
        pass


@registry.register_doc_type("judgment")
class JudgmentDetailView(BaseDocumentDetailView):
    model = Judgment
    template_name = "peachjam/judgment_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["judges"] = (
            self.get_object()
            .bench.prefetch_related("judge")
            .values_list("judge__name", flat=True)
        )
        self.add_case_histories(context)
        return context

    def add_case_histories(self, context):
        document = self.get_object()

        # judgments that impact this one
        histories = [
            {
                "document": ch.judgment_work.documents.first(),
                "children": [
                    {
                        "case_history": ch,
                        "document": document,
                    }
                ],
            }
            for ch in document.work.incoming_case_histories.select_related(
                "court", "historical_judgment_work", "outcome"
            )
            # ignore incoming history entries for dangling works that don't have a document
            if ch.judgment_work.documents.first()
        ]

        if histories:
            context["notices"].append(
                {
                    "type": messages.WARNING,
                    "html": mark_safe(
                        _(
                            "This judgment was reviewed by another court. See the Case history tab for details."
                        )
                    ),
                }
            )

        # judgments that this one impacts
        outgoing_histories = [
            {
                "case_history": ch,
                "document": ch.historical_judgment_work.documents.first()
                if ch.historical_judgment_work
                else None,
            }
            for ch in document.work.case_histories.select_related(
                "historical_judgment_work", "outcome"
            ).prefetch_related(
                "historical_judgment_work__documents",
                "historical_judgment_work__documents__outcomes",
                "historical_judgment_work__documents__court",
                "historical_judgment_work__documents__judges",
            )
        ]
        if outgoing_histories:
            histories.append(
                {
                    "document": document,
                    "children": outgoing_histories,
                }
            )

        today = now().date()
        for history in histories:
            for child in history["children"]:
                child["info"] = child["document"] or child["case_history"]

            # sort by date descending
            history["children"].sort(
                key=lambda x: x["info"].date or today, reverse=True
            )

        # sort by date descending
        histories.sort(key=lambda x: x["document"].date, reverse=True)

        context["case_histories"] = histories

        return histories
