"""peachjam URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path, register_converter
from django.views.decorators.cache import cache_page

from peachjam.feeds import (
    ArticleAtomSiteNewsFeed,
    CoreDocumentAtomSiteNewsFeed,
    GenericDocumentAtomSiteNewsFeed,
    JudgmentAtomSiteNewsFeed,
    LegalInstrumentAtomSiteNewsFeed,
    LegislationAtomSiteNewsFeed,
)
from peachjam.helpers import ISODateConverter
from peachjam.views import (
    AboutPageView,
    ArticleDetailView,
    ArticleListView,
    ArticleTopicListView,
    ArticleYearArchiveView,
    AuthorDetailView,
    BookListView,
    CourtClassDetailView,
    CourtClassMonthView,
    CourtClassYearView,
    CourtDetailView,
    CourtMonthView,
    CourtRegistryDetailView,
    CourtRegistryMonthView,
    CourtRegistryYearView,
    CourtYearView,
    DocumentDetailViewResolver,
    DocumentListView,
    DocumentMediaView,
    DocumentNatureListView,
    DocumentPopupView,
    DocumentProblemView,
    DocumentSourcePDFView,
    DocumentSourceView,
    FolderCreateView,
    FolderDeleteView,
    FolderListView,
    FolderUpdateView,
    GazetteListView,
    GazetteYearView,
    HomePageView,
    JournalListView,
    JudgmentListView,
    JudgmentWorksAutocomplete,
    LegalInstrumentListView,
    LegislationListView,
    PeachjamAdminLoginView,
    PlaceDetailView,
    PocketLawResources,
    RobotsView,
    SavedDocumentButtonView,
    SavedDocumentCreateView,
    SavedDocumentDeleteView,
    SavedDocumentUpdateView,
    TaxonomyDetailView,
    TaxonomyFirstLevelView,
    TaxonomyListView,
    TermsOfUsePageView,
    UserProfileDetailView,
    WorkAutocomplete,
)
from peachjam.views.comments import comment_form_view
from peachjam.views.generic_views import CSRFTokenView
from peachjam.views.metabase_stats import MetabaseStatsView

register_converter(ISODateConverter, "isodate")


# cache duration for most cached pages
CACHE_DURATION = 60 * 60 * 24

urlpatterns = [
    path("", HomePageView.as_view(), name="home_page"),
    path("_token", CSRFTokenView.as_view(), name="csrf_token"),
    path("terms-of-use/", TermsOfUsePageView.as_view(), name="terms_of_use"),
    path(
        "about/",
        AboutPageView.as_view(),
        name="about",
    ),
    # listing views
    path(
        "authors/<slug:code>/",
        AuthorDetailView.as_view(),
        name="author",
    ),
    path("judgments/", JudgmentListView.as_view(), name="judgment_list"),
    path(
        "judgments/court-class/<str:court_class>/",
        CourtClassDetailView.as_view(),
        name="court_class",
    ),
    path(
        "judgments/court-class/<str:court_class>/<int:year>/",
        CourtClassYearView.as_view(),
        name="court_class_year",
    ),
    path(
        "judgments/court-class/<str:court_class>/<int:year>/<int:month>/",
        CourtClassMonthView.as_view(),
        name="court_class_month",
    ),
    path(
        "judgments/<str:code>/",
        CourtDetailView.as_view(),
        name="court",
    ),
    path(
        "judgments/<str:code>/<int:year>/",
        CourtYearView.as_view(),
        name="court_year",
    ),
    path(
        "judgments/<str:code>/<int:year>/<int:month>/",
        CourtMonthView.as_view(),
        name="court_month",
    ),
    path(
        "judgments/<str:code>/<str:registry_code>/",
        CourtRegistryDetailView.as_view(),
        name="court_registry",
    ),
    path(
        "judgments/<str:code>/<str:registry_code>/<int:year>/",
        CourtRegistryYearView.as_view(),
        name="court_registry_year",
    ),
    path(
        "judgments/<str:code>/<str:registry_code>/<int:year>/<int:month>/",
        CourtRegistryMonthView.as_view(),
        name="court_registry_month",
    ),
    path("place/<str:code>", PlaceDetailView.as_view(), name="place"),
    path("legislation/", LegislationListView.as_view(), name="legislation_list"),
    path(
        "legal_instruments/",
        LegalInstrumentListView.as_view(),
        name="legal_instrument_list",
    ),
    path("gazettes", GazetteListView.as_view(), name="gazettes"),
    path(
        "gazettes/<str:code>/", GazetteListView.as_view(), name="gazettes_by_locality"
    ),
    path("gazettes/<int:year>", GazetteYearView.as_view(), name="gazettes_by_year"),
    path(
        "gazettes/<str:code>/<int:year>",
        GazetteYearView.as_view(),
        name="gazettes_by_year",
    ),
    path(
        "doc/",
        DocumentListView.as_view(),
        name="generic_document_list",
    ),
    path("books/", BookListView.as_view(), name="book_list"),
    path("journals/", JournalListView.as_view(), name="journal_list"),
    path("taxonomy/", TaxonomyListView.as_view(), name="top_level_taxonomy_list"),
    path(
        "taxonomy/<slug:topic>",
        TaxonomyFirstLevelView.as_view(),
        name="first_level_taxonomy_list",
    ),
    path(
        "taxonomy/<slug:topic>/<slug:child>",
        TaxonomyDetailView.as_view(),
        name="taxonomy_detail",
    ),
    # document detail views
    re_path(
        r"^(?P<frbr_uri>akn/.*)/source$",
        cache_page(CACHE_DURATION)(DocumentSourceView.as_view()),
        name="document_source",
    ),
    re_path(
        r"^(?P<frbr_uri>akn/.*)/source.pdf$",
        cache_page(CACHE_DURATION)(DocumentSourcePDFView.as_view()),
        name="document_source_pdf",
    ),
    re_path(
        r"^(?P<frbr_uri>akn/.*)/media/(?P<filename>.+)$",
        cache_page(CACHE_DURATION)(DocumentMediaView.as_view()),
        name="document_media",
    ),
    re_path(
        r"^(?P<frbr_uri>akn/?.*)$",
        DocumentDetailViewResolver.as_view(),
        name="document_detail",
    ),
    # feeds
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
    path("feeds/articles.xml", ArticleAtomSiteNewsFeed(), name="article_feed"),
    # separate apps
    path("search/", include(("peachjam_search.urls", "search"), namespace="search")),
    path(
        "admin/login/",
        PeachjamAdminLoginView.as_view(),
        name="login",
    ),
    # autocomplete for admin area
    path(
        "admin/autocomplete/works",
        WorkAutocomplete.as_view(),
        name="autocomplete-works",
    ),
    path(
        "admin/autocomplete/judgments",
        JudgmentWorksAutocomplete.as_view(),
        name="autocomplete-judgment-works",
    ),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("api/", include("peachjam_api.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("articles/", ArticleListView.as_view(), name="article_list"),
    path(
        "articles/<slug:topic>",
        ArticleTopicListView.as_view(),
        name="article_topic_list",
    ),
    path(
        "articles/<isodate:date>/<str:author>/<slug:slug>",
        ArticleDetailView.as_view(),
        name="article_detail",
    ),
    path(
        "articles/<int:year>/",
        ArticleYearArchiveView.as_view(),
        name="article_year_archive",
    ),
    path("users/<username>", UserProfileDetailView.as_view(), name="user_profile"),
    path(
        "robots.txt",
        RobotsView.as_view(
            template_name="peachjam/robots.txt", content_type="text/plain"
        ),
    ),
    path(
        "pocketlaw-resources", PocketLawResources.as_view(), name="pocketlaw_resources"
    ),
    re_path(
        r"^doc/(?P<nature>[\w-]+)$",
        DocumentNatureListView.as_view(),
        name="document_nature_list",
    ),
    # law-widget support services
    path(
        "p/<str:partner>/e/popup/<path:frbr_uri>",
        cache_page(CACHE_DURATION)(DocumentPopupView.as_view()),
    ),
    path("stats", MetabaseStatsView.as_view(), name="metabase_stats"),
    path(
        "document-problem/",
        DocumentProblemView.as_view(),
        name="document_problem",
    ),
    # Saved Documents
    path(
        "saved-documents/button/<int:doc_id>",
        SavedDocumentButtonView.as_view(),
        name="saved_document_button",
    ),
    path(
        "saved-documents/create",
        SavedDocumentCreateView.as_view(),
        name="saved_document_create",
    ),
    path(
        "saved-documents/<int:pk>/update",
        SavedDocumentUpdateView.as_view(),
        name="saved_document_update",
    ),
    path(
        "saved-documents/<int:pk>/delete",
        SavedDocumentDeleteView.as_view(),
        name="saved_document_delete",
    ),
    path(
        "saved-documents/folders/",
        FolderListView.as_view(),
        name="folder_list",
    ),
    path(
        "saved-documents/folders/create",
        FolderCreateView.as_view(),
        name="folder_create",
    ),
    path(
        "saved-documents/folders/<int:pk>/update",
        FolderUpdateView.as_view(),
        name="folder_update",
    ),
    path(
        "saved-documents/folders/<int:pk>/delete",
        FolderDeleteView.as_view(),
        name="folder_delete",
    ),
    # django-markdown-editor
    path("martor/", include("martor.urls")),
    path(
        "comments/",
        include(
            [
                path("", include("django_comments.urls")),
                path(
                    "form/<str:app_label>/<str:model_name>/<int:pk>",
                    comment_form_view,
                    name="comment_form",
                ),
            ]
        ),
    ),
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
