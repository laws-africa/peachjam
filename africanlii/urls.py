from django.conf.urls.i18n import i18n_patterns
from django.urls import include, path
from django.views.generic import RedirectView

from africanlii import views

urlpatterns = i18n_patterns(
    *[
        path("", views.HomePageView.as_view(), name="home_page"),
        path("soft-law/", views.AGPSoftLawListView.as_view(), name="agp_soft_law_list"),
        path(
            "doc/",
            views.AGPReportsGuidesListView.as_view(),
            name="agp_reports_guides_list",
        ),
        path(
            "legal-instruments/",
            RedirectView.as_view(
                permanent=True,
                url="/taxonomy/african-union-collections/african-union-collections-legal-instruments",
            ),
            name="agp_legal_instrument_list",
        ),
        path("au/", views.AfricanUnionDetailPageView.as_view(), name="au_detail_page"),
        path(
            "au/au-organs/<slug:code>/",
            views.AfricanUnionOrganDetailView.as_view(),
            name="au_organ_detail_view",
        ),
        path(
            "au/au-institution/<slug:code>/",
            views.AfricanUnionInstitutionDetailView.as_view(),
            name="au_institution_detail_view",
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
        path(
            "mooc/",
            views.AGPMOOCView.as_view(),
            name="mooc_landing_page",
        ),
        # redirects for legacy africanlii.org URLS
        path(
            "commercial",
            RedirectView.as_view(
                permanent=True, url="/indexes/case-indexes/case-indexes-commercial"
            ),
        ),
        path(
            "environmental",
            RedirectView.as_view(
                permanent=True, url="/indexes/case-indexes/case-indexes-environmental"
            ),
        ),
        path(
            "humanrights",
            RedirectView.as_view(
                permanent=True, url="/indexes/case-indexes/case-indexes-human-rights"
            ),
        ),
        path("article", RedirectView.as_view(permanent=True, url="/articles")),
        path("article/<path:path>", views.ArticleRedirectView.as_view()),
        # peachjam site URLS
        path("", include("peachjam.urls.i18n")),
    ]
) + [
    # peachjam site URLS
    path("", include("peachjam.urls.non_i18n")),
]
