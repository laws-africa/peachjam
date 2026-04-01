from collections import defaultdict
from functools import cached_property

from django.db.models import F, Window
from django.db.models.functions import RowNumber
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from peachjam.helpers import get_language
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

    @cached_property
    def volume_judgment_work_ids(self):
        return (
            Judgment.objects.filter(
                law_report_entries__law_report_volume=self.law_report_volume,
                published=True,
            )
            .values_list("work_id", flat=True)
            .distinct()
        )

    @cached_property
    def cited_work_ids(self):
        return (
            ExtractedCitation.objects.filter(
                citing_work_id__in=self.volume_judgment_work_ids
            )
            .values_list("target_work_id", flat=True)
            .distinct()
        )

    def get_base_queryset(self, exclude=None):
        return self.get_model_queryset().filter(work_id__in=self.cited_work_ids)

    def add_facets(self, context):
        context["facet_data"] = {}
        self.add_alphabet_facet(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["doc_table_toggle"] = self.doc_table_toggle
        context["doc_table_show_jurisdiction"] = self.doc_table_show_jurisdiction
        context["documents"] = self.group_documents(context["documents"])
        self.attach_citing_judgments(context["documents"])
        return context

    def attach_citing_judgments(self, cited_docs):
        """Attach citing judgments from this volume as .children for toggle."""
        work_ids = [d.work_id for d in cited_docs if hasattr(d, "work_id")]
        if not work_ids:
            return

        citations = (
            ExtractedCitation.objects.filter(
                citing_work_id__in=self.volume_judgment_work_ids,
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
    template_name = "peachjam/law_report/law_report_volume_cases_index.html"
    active_tab = "cases"
    model = Judgment
    queryset = Judgment.objects.prefetch_related(
        "judges", "labels", "attorneys", "outcomes"
    ).select_related("work")


class LawReportVolumeLegislationIndexView(LawReportVolumeCitationIndexBaseView):
    template_name = "peachjam/law_report/law_report_volume_legislation_index.html"
    active_tab = "legislation"
    model = Legislation

    def get_queryset(self):
        qs = self.get_base_queryset().preferred_language(get_language(self.request))
        filtered_qs = self.filter_queryset(qs, filter_q=True)
        latest_ids = filtered_qs.annotate(
            row_number=Window(
                expression=RowNumber(),
                partition_by=[F("work_id")],
                order_by=[F("date").desc(), F("pk").desc()],
            )
        ).filter(row_number=1)
        return self.form.order_queryset(qs.filter(pk__in=latest_ids.values("pk")))
