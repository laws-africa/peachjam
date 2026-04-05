from django.urls import path

from peachjam.views import (
    LawReportDetailView,
    LawReportListView,
    LawReportVolumeCasesIndexView,
    LawReportVolumeDetailView,
    LawReportVolumeLegislationIndexView,
)

urlpatterns = [
    path("", LawReportListView.as_view(), name="law_report_list"),
    path("<slug:slug>/", LawReportDetailView.as_view(), name="law_report_detail"),
    path(
        "<slug:slug>/volumes/<slug:volume_slug>/",
        LawReportVolumeDetailView.as_view(),
        name="law_report_volume_detail",
    ),
    path(
        "<slug:slug>/volumes/<slug:volume_slug>/cases-index/",
        LawReportVolumeCasesIndexView.as_view(),
        name="law_report_volume_cases_index",
    ),
    path(
        "<slug:slug>/volumes/<slug:volume_slug>/legislation-index/",
        LawReportVolumeLegislationIndexView.as_view(),
        name="law_report_volume_legislation_index",
    ),
]
