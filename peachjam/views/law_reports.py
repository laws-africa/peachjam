from functools import cached_property

from django.shortcuts import get_object_or_404
from django.views.generic import ListView

from peachjam.helpers import chunks
from peachjam.models import LawReport, LawReportVolume
from peachjam.views.courts import FilteredJudgmentView


class LawReportListView(ListView):
    template_name = "peachjam/law_report/law_report_list.html"
    model = LawReport
    context_object_name = "law_reports"


class BaseLawReportDetailView(FilteredJudgmentView):
    template_name = "peachjam/law_report/law_report_detail.html"
    navbar_link = "law_report"

    @cached_property
    def law_report(self):
        return get_object_or_404(
            LawReport.objects.prefetch_related("volumes"), slug=self.kwargs.get("slug")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["law_report"] = self.law_report
        context["law_report_volumes"] = self.law_report.volumes.exclude(
            law_report_entries__isnull=True
        )
        context["law_report_volume_groups"] = chunks(context["law_report_volumes"], 3)
        context["hide_follow_button"] = True
        return context


class LawReportDetailView(BaseLawReportDetailView):
    def base_view_name(self):
        return self.law_report.title

    def get_base_queryset(self, exclude=None):
        qs = super().get_base_queryset(exclude=exclude)
        qs = qs.filter(
            law_report_entries__law_report_volume__law_report=self.law_report
        )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entity_profile"] = self.law_report.entity_profile.first()
        context["entity_profile_title"] = self.law_report.title
        return context


class LawReportVolumeDetailView(BaseLawReportDetailView):
    def base_view_name(self):
        return self.law_report_volume.title

    @cached_property
    def law_report_volume(self):
        return get_object_or_404(
            LawReportVolume,
            law_report=self.law_report,
            slug=self.kwargs.get("volume_slug"),
        )

    def get_base_queryset(self, exclude=None):
        qs = super().get_base_queryset(exclude=exclude)
        qs = qs.filter(law_report_entries__law_report_volume=self.law_report_volume)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["law_report_volume"] = self.law_report_volume
        return context
