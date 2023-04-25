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
    path("au/", views.AfricanUnionDetailPageView.as_view(), name="au_detail_page"),
    # path("au-organs/<int:pk>/", views.AfricanUnionOrganDetailView.as_view(), name="au_organ_detail_view"),
    path("", include("peachjam.urls")),
]
