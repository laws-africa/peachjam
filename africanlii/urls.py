from django.urls import include, path

from africanlii import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    path("soft-law/", views.AGPSoftLawListView.as_view(), name="agp_soft_law_list"),
    path(
        "doc/", views.AGPReportsGuidesListView.as_view(), name="agp_reports_guides_list"
    ),
    path(
        "legal-instruments/",
        views.AGPLegalInstrumentListView.as_view(),
        name="agp_legal_instrument_list",
    ),
    path(
        "case-index/<slug:topic>",
        views.CaseIndexDetailView.as_view(),
        name="case_index_detail",
    ),
    path(
        "case-index/<slug:first_level_topic>/<path:topics>",
        views.CaseIndexChildDetailView.as_view(),
        name="case_index_child_detail",
    ),
    path("", include("peachjam.urls")),
]
