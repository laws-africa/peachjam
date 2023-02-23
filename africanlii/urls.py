from django.urls import include, path

from africanlii import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    path(
        "legislation/", views.AGPLegislationListView.as_view(), name="legislation_list"
    ),
    path("soft-law/", views.AGPSoftLawListView.as_view(), name="agp_soft_law_list"),
    path(
        "doc/", views.AGPReportsGuidesListView.as_view(), name="agp_reports_guides_list"
    ),
    path(
        "legal-instruments/",
        views.AGPLegalInstrumentListView.as_view(),
        name="agp_legal_instrument_list",
    ),
    path("", include("peachjam.urls")),
]
