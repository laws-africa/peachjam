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
        "indexes/",
        views.DocIndexesListView.as_view(),
        name="doc_index_list",
    ),
    path(
        "indexes/<slug:first_level_topic>/<path:topics>",
        views.DocIndexDetailView.as_view(),
        name="doc_index_detail",
    ),
    path("", include("peachjam.urls")),
]
