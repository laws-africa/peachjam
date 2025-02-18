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
    LegislationAtomSiteNewsFeed,
)
from peachjam.helpers import ISODateConverter
from peachjam.views import (
    AboutPageView,
    AnnotationDeleteView,
    AnnotationDetailView,
    AnnotationEditView,
    AnnotationListView,
    ArticleAttachmentDetailView,
    ArticleAuthorDetailView,
    ArticleAuthorYearDetailView,
    ArticleDetailView,
    ArticleListView,
    ArticleTopicView,
    ArticleTopicYearView,
    ArticleYearView,
    AuthorDetailView,
    BillListView,
    BookListView,
    CauseListCourtClassMonthView,
    CauseListCourtClassView,
    CauseListCourtClassYearView,
    CauseListCourtDetailView,
    CauseListCourtMonthView,
    CauseListCourtRegistryDetailView,
    CauseListCourtRegistryMonthView,
    CauseListCourtRegistryYearView,
    CauseListCourtYearView,
    CauseListListView,
    ComparePortionsView,
    CourtClassDetailView,
    CourtClassMonthView,
    CourtClassYearView,
    CourtDetailView,
    CourtMonthView,
    CourtRegistryDetailView,
    CourtRegistryMonthView,
    CourtRegistryYearView,
    CourtYearView,
    DocumentAnonymiseAPIView,
    DocumentAnonymiseSuggestionsAPIView,
    DocumentAnonymiseView,
    DocumentCitationsView,
    DocumentDetailViewResolver,
    DocumentListView,
    DocumentMediaView,
    DocumentNatureListView,
    DocumentPopupView,
    DocumentProblemView,
    DocumentPublicationView,
    DocumentSourcePDFView,
    DocumentSourceView,
    EditAccountView,
    FolderCreateView,
    FolderDeleteView,
    FolderListView,
    FolderUpdateView,
    GazetteListView,
    GazetteYearView,
    GetAccountView,
    HomePageView,
    JournalListView,
    JudgesAutocomplete,
    JudgmentListView,
    JudgmentWorksAutocomplete,
    LegislationListView,
    PartnerLogoView,
    PeachjamAdminLoginView,
    PlaceBillListView,
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
    WorkAutocomplete,
)
from peachjam.views.comments import comment_form_view
from peachjam.views.document_access_group import (
    DocumentAccessGroupDetailView,
    DocumentAccessGroupListView,
)
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
    path(
        "judgments/",
        include(
            [
                path("", JudgmentListView.as_view(), name="judgment_list"),
                path(
                    "court-class/<str:court_class>/",
                    CourtClassDetailView.as_view(),
                    name="court_class",
                ),
                path(
                    "court-class/<str:court_class>/<int:year>/",
                    CourtClassYearView.as_view(),
                    name="court_class_year",
                ),
                path(
                    "court-class/<str:court_class>/<int:year>/<int:month>/",
                    CourtClassMonthView.as_view(),
                    name="court_class_month",
                ),
                path(
                    "<str:code>/",
                    CourtDetailView.as_view(),
                    name="court",
                ),
                path(
                    "<str:code>/<int:year>/",
                    CourtYearView.as_view(),
                    name="court_year",
                ),
                path(
                    "<str:code>/<int:year>/<int:month>/",
                    CourtMonthView.as_view(),
                    name="court_month",
                ),
                path(
                    "<str:code>/<str:registry_code>/",
                    CourtRegistryDetailView.as_view(),
                    name="court_registry",
                ),
                path(
                    "<str:code>/<str:registry_code>/<int:year>/",
                    CourtRegistryYearView.as_view(),
                    name="court_registry_year",
                ),
                path(
                    "<str:code>/<str:registry_code>/<int:year>/<int:month>/",
                    CourtRegistryMonthView.as_view(),
                    name="court_registry_month",
                ),
            ]
        ),
    ),
    path(
        "causelists/",
        include(
            [
                path("", CauseListListView.as_view(), name="causelist_list"),
                path(
                    "<str:code>/",
                    CauseListCourtDetailView.as_view(),
                    name="causelist_court",
                ),
                path(
                    "court-class/<str:court_class>/",
                    CauseListCourtClassView.as_view(),
                    name="causelist_court_class",
                ),
                path(
                    "court-class/<str:court_class>/<int:year>/",
                    CauseListCourtClassYearView.as_view(),
                    name="causelist_court_class_year",
                ),
                path(
                    "court-class/<str:court_class>/<int:year>/<int:month>/",
                    CauseListCourtClassMonthView.as_view(),
                    name="causelist_court_class_month",
                ),
                path(
                    "<str:code>/<int:year>/",
                    CauseListCourtYearView.as_view(),
                    name="causelist_court_year",
                ),
                path(
                    "<str:code>/<int:year>/<int:month>/",
                    CauseListCourtMonthView.as_view(),
                    name="causelist_court_month",
                ),
                path(
                    "<str:code>/<str:registry_code>/",
                    CauseListCourtRegistryDetailView.as_view(),
                    name="causelist_court_registry",
                ),
                path(
                    "<str:code>/<str:registry_code>/<int:year>/",
                    CauseListCourtRegistryYearView.as_view(),
                    name="causelist_court_registry_year",
                ),
                path(
                    "<str:code>/<str:registry_code>/<int:year>/<int:month>/",
                    CauseListCourtRegistryMonthView.as_view(),
                    name="causelist_court_registry_month",
                ),
            ]
        ),
    ),
    path("place/<str:code>", PlaceDetailView.as_view(), name="place"),
    path("legislation/", LegislationListView.as_view(), name="legislation_list"),
    path(
        "bills/",
        include(
            [
                path("", BillListView.as_view(), name="bill_list"),
                path("<str:code>", PlaceBillListView.as_view(), name="place_bill_list"),
            ]
        ),
    ),
    path(
        "gazettes/",
        include(
            [
                path("", GazetteListView.as_view(), name="gazettes"),
                path(
                    "<str:code>/",
                    GazetteListView.as_view(),
                    name="gazettes_by_locality",
                ),
                path("<int:year>", GazetteYearView.as_view(), name="gazettes_by_year"),
                path(
                    "<str:code>/<int:year>",
                    GazetteYearView.as_view(),
                    name="gazettes_by_year",
                ),
            ]
        ),
    ),
    path(
        "doc/",
        DocumentListView.as_view(),
        name="generic_document_list",
    ),
    path("books/", BookListView.as_view(), name="book_list"),
    path("journals/", JournalListView.as_view(), name="journal_list"),
    path(
        "taxonomy/",
        include(
            [
                path("", TaxonomyListView.as_view(), name="top_level_taxonomy_list"),
                path(
                    "<slug:topic>",
                    TaxonomyFirstLevelView.as_view(),
                    name="first_level_taxonomy_list",
                ),
                path(
                    "<slug:topic>/<slug:child>",
                    TaxonomyDetailView.as_view(),
                    name="taxonomy_detail",
                ),
            ]
        ),
    ),
    # document detail views
    re_path(
        r"^(?P<frbr_uri>akn/.*)/source$",
        cache_page(CACHE_DURATION)(DocumentSourceView.as_view()),
        name="document_source",
    ),
    re_path(
        r"^(?P<frbr_uri>akn/.*)/publication$",
        cache_page(CACHE_DURATION)(DocumentPublicationView.as_view()),
        name="document_publication",
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
        r"^(?P<frbr_uri>akn/.*)/citations$",
        cache_page(CACHE_DURATION)(DocumentCitationsView.as_view()),
        name="document_citations",
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
    path(
        "admin/",
        include(
            [
                # autocomplete for admin area
                path(
                    "autocomplete/works",
                    WorkAutocomplete.as_view(),
                    name="autocomplete-works",
                ),
                path(
                    "autocomplete/judges",
                    JudgesAutocomplete.as_view(),
                    name="autocomplete-judges",
                ),
                path(
                    "autocomplete/judgments",
                    JudgmentWorksAutocomplete.as_view(),
                    name="autocomplete-judgment-works",
                ),
                path("anon/<int:pk>", DocumentAnonymiseView.as_view(), name="anon"),
                path("anon/<int:pk>/update", DocumentAnonymiseAPIView.as_view()),
                path(
                    "anon/<int:pk>/suggestions",
                    DocumentAnonymiseSuggestionsAPIView.as_view(),
                ),
                path("", admin.site.urls),
            ]
        ),
    ),
    path("accounts/", include("allauth.urls")),
    path("accounts/profile/", EditAccountView.as_view(), name="edit_account"),
    path("accounts/user/", GetAccountView.as_view(), name="get_account"),
    path("api/", include("peachjam_api.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path(
        "articles/",
        include(
            [
                path("", ArticleListView.as_view(), name="article_list"),
                path(
                    "authors/<username>",
                    ArticleAuthorDetailView.as_view(),
                    name="article_author",
                ),
                path(
                    "authors/<username>/<int:year>",
                    ArticleAuthorYearDetailView.as_view(),
                    name="article_author_year",
                ),
                path(
                    "<int:year>",
                    ArticleYearView.as_view(),
                    name="article_year_archive",
                ),
                path(
                    "<slug:topic>",
                    ArticleTopicView.as_view(),
                    name="article_topic",
                ),
                path(
                    "<slug:topic>/<int:year>",
                    ArticleTopicYearView.as_view(),
                    name="article_topic_year",
                ),
                path(
                    "<isodate:date>/<str:author>/<slug:slug>",
                    ArticleDetailView.as_view(),
                    name="article_detail",
                ),
                path(
                    "<isodate:date>/<str:author>/<slug:slug>/attachment/<int:pk>/<str:filename>",
                    ArticleAttachmentDetailView.as_view(),
                    name="article_attachment",
                ),
            ]
        ),
    ),
    path(
        "partners/<int:pk>/logo/<int:logo_pk>",
        PartnerLogoView.as_view(),
        name="partner_logo",
    ),
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
    # Restricted Documents
    path(
        "document-access-groups/",
        DocumentAccessGroupListView.as_view(),
        name="document_access_group_list",
    ),
    path(
        "document-access-groups/<int:pk>",
        DocumentAccessGroupDetailView.as_view(),
        name="document_access_group_detail",
    ),
    # Annotations
    path(
        "annotations/",
        include(
            [
                path(
                    "",
                    AnnotationListView.as_view(),
                    name="annotation_list",
                ),
                path(
                    "<int:pk>/",
                    AnnotationDetailView.as_view(),
                    name="annotation_detail",
                ),
                path(
                    "<int:pk>/edit",
                    AnnotationEditView.as_view(),
                    name="annotation_edit",
                ),
                path(
                    "<int:pk>/delete",
                    AnnotationDeleteView.as_view(),
                    name="annotation_delete",
                ),
            ]
        ),
    ),
    path(
        "compare",
        ComparePortionsView.as_view(),
        name="compare_portions",
    ),
    # django-markdown-editor
    path("martor/", include("martor.urls")),
    path(
        "comments/",
        include(
            [
                path("", include("django_comments.urls")),
                path(
                    "form/<str:app_label>/<str:model_name>/<slug:pk>",
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
