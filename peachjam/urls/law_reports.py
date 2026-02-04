from django.urls import path

from peachjam.views import (
    LawReportDetailView,
    LawReportListView,
    LawReportVolumeDetailView,
)

urlpatterns = [
    path("", LawReportListView.as_view(), name="law_report_list"),
    path("<slug:slug>/", LawReportDetailView.as_view(), name="law_report_detail"),
    path(
        "<slug:slug>/volumes/<slug:volume_slug>/",
        LawReportVolumeDetailView.as_view(),
        name="law_report_volume_detail",
    ),
]
