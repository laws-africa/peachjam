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
    path(
        "au/au-organs/<slug:code>/",
        views.AfricanUnionOrganDetailView.as_view(),
        name="au_organ_detail_view",
    ),
    path(
        "au/rec/<slug:code>/",
        views.RegionalEconomicCommunityDetailView.as_view(),
        name="rec_detail_view",
    ),
    path(
        "au/member-state/<slug:country>/",
        views.MemberStateDetailView.as_view(),
        name="member_state_detail_view",
    ),
    path(
        "indexes/",
        views.DocIndexesListView.as_view(),
        name="doc_index_list",
    ),
    path(
        "indexes/<slug:topic>",
        views.DocIndexFirstLevelView.as_view(),
        name="doc_index_first_level",
    ),
    path(
        "indexes/<slug:topic>/<slug:child>",
        views.DocIndexDetailView.as_view(),
        name="doc_index_detail",
    ),
    path(
        "taxonomy/<slug:topic>",
        views.CustomTaxonomyFirstLevelView.as_view(),
        name="first_level_taxonomy_list",
    ),
    path(
        "taxonomy/<slug:topic>/<slug:child>",
        views.CustomTaxonomyDetailView.as_view(),
        name="taxonomy_detail",
    ),
    path("", include("peachjam.urls")),
]
