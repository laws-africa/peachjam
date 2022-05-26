from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.views.decorators.cache import cache_page

from africanlii import views
from africanlii.feeds import (
    CoreDocumentAtomSiteNewsFeed,
    GenericDocumentAtomSiteNewsFeed,
    JudgmentAtomSiteNewsFeed,
    LegalInstrumentAtomSiteNewsFeed,
    LegislationAtomSiteNewsFeed,
)

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    path("", include("peachjam.urls")),
    path("judgments/", views.JudgmentListView.as_view(), name="judgment_list"),
    path("legislation/", views.LegislationListView.as_view(), name="legislation_list"),
    path(
        "legal_instruments/",
        views.LegalInstrumentListView.as_view(),
        name="legal_instrument_list",
    ),
    path(
        "about/",
        views.AboutPageView.as_view(),
        name="about",
    ),
    path(
        "generic_documents/",
        views.GenericDocumentListView.as_view(),
        name="generic_document_list",
    ),
    path(
        "documents<path:expression_frbr_uri>/",
        views.DocumentDetailViewResolver.as_view(),
        name="document_detail",
    ),
    path(
        "documents<path:expression_frbr_uri>/source.pdf",
        cache_page(60 * 60 * 6)(views.DocumentSourceView.as_view()),
        name="document_source",
    ),
    path("feeds/judgments.xml", JudgmentAtomSiteNewsFeed(), name="judgment_feed"),
    path(
        "feeds/generic_documents.xml",
        GenericDocumentAtomSiteNewsFeed(),
        name="generic_document_feed",
    ),
    path(
        "feeds/legal_instruments.xml",
        LegalInstrumentAtomSiteNewsFeed(),
        name="legal_instrument_feed",
    ),
    path(
        "feeds/legislation.xml", LegislationAtomSiteNewsFeed(), name="legislation_feed"
    ),
    path("feeds/all.xml", CoreDocumentAtomSiteNewsFeed(), name="atom_feed"),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = (
        [
            path("__debug__/", include(debug_toolbar.urls)),
        ]
        + urlpatterns
        + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    )
