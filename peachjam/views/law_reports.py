from collections import defaultdict
from functools import cached_property

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, ListView

from peachjam.models import (
    ExtractedCitation,
    Judgment,
    LawReport,
    LawReportVolume,
    Legislation,
)
from peachjam.views.courts import FilteredJudgmentView


class LawReportListView(ListView):
    template_name = "peachjam/law_report/law_report_list.html"
    model = LawReport
    context_object_name = "law_reports"


class LawReportDetailView(DetailView):
    template_name = "peachjam/law_report/law_report_detail.html"
    model = LawReport
    context_object_name = "law_report"
    navbar_link = "law_report"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["law_report_volumes"] = self.object.volumes.exclude(
            law_report_entries__isnull=True
        ).order_by("-title")
        context["entity_profile"] = self.object.entity_profile.first()
        context["entity_profile_title"] = self.object.title
        return context


class LawReportVolumeDetailView(FilteredJudgmentView):
    template_name = "peachjam/law_report/law_report_volume_detail.html"
    navbar_link = "law_report"
    tab_name = "judgments"

    CITATION_TABS = {"cases": Judgment, "legislation": Legislation}
    TAB_METADATA = {
        "judgments": {
            "doc_count_noun": _("judgment"),
            "doc_count_noun_plural": _("judgments"),
            "doc_table_date_label": _("Judgment date"),
            "page_title": None,
        },
        "cases": {
            "doc_count_noun": _("case"),
            "doc_count_noun_plural": _("cases"),
            "doc_table_date_label": _("Judgment date"),
            "page_title": _("Cited cases"),
        },
        "legislation": {
            "doc_count_noun": _("document"),
            "doc_count_noun_plural": _("documents"),
            "doc_table_date_label": _("Date"),
            "page_title": _("Cited legislation"),
            "nature": _("Legislation"),
        },
    }

    @cached_property
    def law_report(self):
        return get_object_or_404(
            LawReport.objects.prefetch_related("volumes"), slug=self.kwargs.get("slug")
        )

    def base_view_name(self):
        return self.law_report_volume.title

    @cached_property
    def law_report_volume(self):
        return get_object_or_404(
            LawReportVolume,
            law_report=self.law_report,
            slug=self.kwargs.get("volume_slug"),
        )

    @cached_property
    def active_tab(self):
        if self.tab_name in {"judgments", *self.CITATION_TABS.keys()}:
            return self.tab_name
        tab = self.request.GET.get("tab")
        return tab if tab in self.CITATION_TABS else "judgments"

    def get_base_queryset(self, exclude=None):
        if self.active_tab in self.CITATION_TABS:
            model = self.CITATION_TABS[self.active_tab]
            volume_lookup = (
                "work__incoming_citations__citing_work__documents"
                "__judgment__law_report_entries__law_report_volume"
            )
            return (
                model.objects.filter(
                    **{volume_lookup: self.law_report_volume},
                    published=True,
                )
                .distinct()
                .order_by("title")
            )
        qs = super().get_base_queryset(exclude=exclude)
        return qs.filter(law_report_entries__law_report_volume=self.law_report_volume)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["law_report"] = self.law_report
        context["law_report_volume"] = self.law_report_volume
        context["active_tab"] = self.active_tab
        metadata = self.TAB_METADATA[self.active_tab]
        context["doc_count_noun"] = metadata["doc_count_noun"]
        context["doc_count_noun_plural"] = metadata["doc_count_noun_plural"]
        context["doc_table_date_label"] = metadata["doc_table_date_label"]
        context["page_title"] = metadata["page_title"] or self.page_title()
        if metadata.get("nature"):
            context["nature"] = metadata["nature"]

        if self.active_tab in self.CITATION_TABS:
            context["doc_table_toggle"] = True
            self.attach_citing_judgments(context.get("documents", []))

        return context

    def add_facets(self, context):
        if self.active_tab in self.CITATION_TABS:
            context["facet_data"] = {}
            self.add_alphabet_facet(context)
        else:
            super().add_facets(context)

    def attach_citing_judgments(self, cited_docs):
        """Attach citing judgments from this volume as .children for toggle."""
        work_ids = [d.work_id for d in cited_docs if hasattr(d, "work_id")]
        if not work_ids:
            return

        citations = (
            ExtractedCitation.objects.filter(
                citing_work__documents__judgment__law_report_entries__law_report_volume=self.law_report_volume,
                target_work_id__in=work_ids,
            )
            .values_list("target_work_id", "citing_work_id")
            .distinct()
        )

        citing_map = defaultdict(set)
        for target_wid, citing_wid in citations:
            citing_map[target_wid].add(citing_wid)

        if not citing_map:
            return

        all_citing_wids = set().union(*citing_map.values())
        citing_docs = {
            j.work_id: j
            for j in Judgment.objects.filter(
                work_id__in=all_citing_wids, published=True
            )
            .distinct("work_frbr_uri")
            .order_by("work_frbr_uri", "-date")
        }

        for doc in cited_docs:
            if hasattr(doc, "work_id"):
                doc.children = sorted(
                    [
                        citing_docs[wid]
                        for wid in citing_map.get(doc.work_id, [])
                        if wid in citing_docs
                    ],
                    key=lambda d: d.title,
                )
