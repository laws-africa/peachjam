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
from peachjam.views.generic_views import FilteredDocumentListView


class LawReportListView(ListView):
    template_name = "peachjam/law_report/law_report_list.html"
    model = LawReport
    context_object_name = "law_reports"
    navbar_link = "law_report"


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


class LawReportVolumeViewMixin:
    navbar_link = "law_report"
    active_tab = None

    def base_view_name(self):
        return self.law_report_volume.title

    @cached_property
    def law_report(self):
        return get_object_or_404(
            LawReport.objects.prefetch_related("volumes"), slug=self.kwargs.get("slug")
        )

    @cached_property
    def law_report_volume(self):
        return get_object_or_404(
            LawReportVolume,
            law_report=self.law_report,
            slug=self.kwargs.get("volume_slug"),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["law_report"] = self.law_report
        context["law_report_volume"] = self.law_report_volume
        context["active_tab"] = self.active_tab
        return context


class LawReportVolumeDetailView(LawReportVolumeViewMixin, FilteredJudgmentView):
    template_name = "peachjam/law_report/law_report_volume_detail.html"
    active_tab = "judgments"

    def get_base_queryset(self, exclude=None):
        qs = super().get_base_queryset(exclude=exclude)
        return qs.filter(law_report_entries__law_report_volume=self.law_report_volume)


class LawReportVolumeCitationIndexBaseView(
    LawReportVolumeViewMixin, FilteredDocumentListView
):
    form_defaults = {"sort": "title"}
    doc_table_toggle = True
    doc_table_show_jurisdiction = False
    page_title_text = None
    doc_count_noun = None
    doc_count_noun_plural = None
    doc_table_title_label = None
    doc_table_date_label = _("Date")
    nature = None

    def get_base_queryset(self, exclude=None):
        volume_lookup = (
            "work__incoming_citations__citing_work__documents"
            "__judgment__law_report_entries__law_report_volume"
        )
        return (
            self.get_model_queryset()
            .filter(**{volume_lookup: self.law_report_volume})
            .distinct()
        )

    def add_facets(self, context):
        context["facet_data"] = {}
        self.add_alphabet_facet(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.page_title_text
        context["doc_count_noun"] = self.doc_count_noun
        context["doc_count_noun_plural"] = self.doc_count_noun_plural
        context["doc_table_date_label"] = self.doc_table_date_label
        context["doc_table_toggle"] = self.doc_table_toggle
        context["doc_table_show_jurisdiction"] = self.doc_table_show_jurisdiction
        context["documents"] = self.group_documents(context["documents"])
        if self.doc_table_title_label:
            context["doc_table_title_label"] = self.doc_table_title_label
        if self.nature:
            context["nature"] = self.nature
        self.attach_citing_judgments(context["documents"])
        return context

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


class LawReportVolumeCasesIndexView(LawReportVolumeCitationIndexBaseView):
    template_name = "peachjam/law_report/law_report_volume_detail.html"
    active_tab = "cases"
    model = Judgment
    queryset = Judgment.objects.prefetch_related(
        "judges", "labels", "attorneys", "outcomes"
    ).select_related("work")
    page_title_text = _("Cited cases")
    doc_count_noun = _("case")
    doc_count_noun_plural = _("cases")
    doc_table_title_label = _("Citation")
    doc_table_date_label = _("Judgment date")
    nature = "Judgment"


class LawReportVolumeLegislationIndexView(LawReportVolumeCitationIndexBaseView):
    template_name = "peachjam/law_report/law_report_volume_detail.html"
    active_tab = "legislation"
    model = Legislation
    page_title_text = _("Cited legislation")
    doc_count_noun = _("document")
    doc_count_noun_plural = _("documents")
    nature = "Legislation"
