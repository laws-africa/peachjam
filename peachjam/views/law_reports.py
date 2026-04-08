from collections import defaultdict
from functools import cached_property
from itertools import batched

from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from django.views.generic import DetailView, ListView

from peachjam.helpers import get_language
from peachjam.models import (
    ExtractedCitation,
    Judgment,
    LawReport,
    LawReportVolume,
)
from peachjam.views.courts import FilteredJudgmentView
from peachjam.views.generic_views import FilteredDocumentListView
from peachjam.views.legislation import LegislationListView


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
        volumes = list(
            self.object.volumes.exclude(law_report_entries__isnull=True).order_by(
                "-title"
            )
        )
        context["law_report_volumes"] = volumes
        context["law_report_volume_columns"] = [
            list(volume_column) for volume_column in batched(volumes, 4)
        ]
        context["entity_profile"] = self.object.entity_profile.first()
        context["entity_profile_title"] = self.object.title
        return context


class LawReportVolumeViewMixin:
    navbar_link = "law_report"
    active_tab = None

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


class LawReportVolumeTableMixin:
    doc_table_children_expanded = False
    doc_table_toggle_title = None

    def update_doc_table_context(self, context):
        if self.doc_table_toggle and not self.doc_table_toggle_title:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} must define doc_table_toggle_title when "
                "doc_table_toggle is enabled."
            )
        context["doc_table_toggle"] = self.doc_table_toggle
        context["doc_table_children_expanded"] = self.doc_table_children_expanded
        context["doc_table_toggle_title"] = self.doc_table_toggle_title


class LawReportVolumeDetailView(
    LawReportVolumeTableMixin, LawReportVolumeViewMixin, FilteredJudgmentView
):
    template_name = "peachjam/law_report/law_report_volume_detail.html"
    active_tab = "judgments"
    doc_table_toggle = False

    def get_base_queryset(self, exclude=None):
        qs = super().get_base_queryset(exclude=exclude)
        return qs.filter(law_report_entries__law_report_volume=self.law_report_volume)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.update_doc_table_context(context)
        return context


class LawReportVolumeCitationIndexMixin(LawReportVolumeTableMixin):
    form_defaults = {"sort": "title"}
    doc_table_children_expanded = True
    doc_table_toggle = True
    doc_table_toggle_title = _("Cited by")
    doc_table_show_jurisdiction = False

    @staticmethod
    def cited_by_group_title(count):
        return ngettext(
            "Cited by %(count)s judgment",
            "Cited by %(count)s judgments",
            count,
        ) % {"count": count}

    def get_document_table_judgments(self, work_ids):
        return {
            judgment.work_id: judgment
            for judgment in Judgment.objects.filter(
                work_id__in=work_ids,
                published=True,
            )
            .preferred_language(get_language(self.request))
            .latest_expression()
            .for_document_table()
        }

    def attach_related_judgments(
        self,
        parent_docs,
        relation_pairs,
        sort_key,
        group_title=None,
    ):
        parent_docs = [doc for doc in parent_docs if getattr(doc, "work_id", None)]
        if not parent_docs:
            return

        related_work_ids_by_parent = defaultdict(set)
        for parent_work_id, child_work_id in relation_pairs:
            related_work_ids_by_parent[parent_work_id].add(child_work_id)

        if not related_work_ids_by_parent:
            return

        related_judgments = self.get_document_table_judgments(
            set().union(*related_work_ids_by_parent.values())
        )

        for parent_doc in parent_docs:
            children = sorted(
                [
                    related_judgments[work_id]
                    for work_id in related_work_ids_by_parent.get(
                        parent_doc.work_id, []
                    )
                    if work_id in related_judgments
                ],
                key=sort_key,
            )
            for child in children:
                child.is_table_child = True
            parent_doc.children = children
            if children:
                if group_title:
                    parent_doc.children_group_row = {
                        "is_group": True,
                        "is_table_child": True,
                        "title": group_title(len(children)),
                    }

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
        return (
            super()
            .get_base_queryset(exclude=exclude)
            .filter(work_id__in=self.cited_work_ids)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.update_doc_table_context(context)
        context["doc_table_show_jurisdiction"] = self.doc_table_show_jurisdiction
        if hasattr(context["documents"], "query"):
            context["documents"] = self.group_documents(context["documents"])
        return context

    def group_documents(self, documents, group_by=None):
        self.attach_citing_judgments(documents)
        return super().group_documents(documents, group_by=group_by)

    def attach_citing_judgments(self, cited_docs):
        """Attach citing judgments from this volume as .children for toggle."""
        work_ids = [d.work_id for d in cited_docs]
        if not work_ids:
            return

        citations = ExtractedCitation.objects.filter(
            citing_work_id__in=self.volume_judgment_work_ids,
            target_work_id__in=work_ids,
        ).values_list("target_work_id", "citing_work_id")

        self.attach_related_judgments(
            cited_docs,
            citations.distinct(),
            lambda doc: doc.title,
            group_title=self.cited_by_group_title,
        )


class LawReportVolumeCasesIndexView(
    LawReportVolumeCitationIndexMixin, LawReportVolumeViewMixin, FilteredJudgmentView
):
    template_name = "peachjam/law_report/law_report_volume_cases_index.html"
    active_tab = "cases"

    def get_form(self):
        return FilteredDocumentListView.get_form(self)


class LawReportVolumeLegislationIndexView(
    LawReportVolumeCitationIndexMixin, LawReportVolumeViewMixin, LegislationListView
):
    template_name = "peachjam/law_report/law_report_volume_legislation_index.html"
    active_tab = "legislation"
    latest_expression_only = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["doc_table_show_doc_type"] = False
        context["doc_table_full_title_width"] = True
        return context
