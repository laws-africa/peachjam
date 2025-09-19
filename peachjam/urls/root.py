from django.urls import include, path, register_converter

from peachjam.helpers import ISODateConverter
from peachjam.views import (
    AboutPageView,
    AuthorDetailView,
    BookListView,
    DocumentUncommencedProvisionListView,
    HomePageView,
    JournalListView,
    LegislationListView,
    PlaceDetailView,
    PocketLawResources,
    TermsOfUsePageView,
    UncommencedProvisionDetailView,
    UncommencedProvisionListView,
    UnconstitutionalProvisionDetailView,
    UnconstitutionalProvisionListView,
)
from peachjam.views.metabase_stats import MetabaseStatsView

register_converter(ISODateConverter, "isodate")


urlpatterns = [
    path("", HomePageView.as_view(), name="home_page"),
    # listing views
    path("articles/", include("peachjam.urls.articles")),
    path("bills/", include("peachjam.urls.bills")),
    path("books/", BookListView.as_view(), name="book_list"),
    path("causelists/", include("peachjam.urls.causelists")),
    path("doc/", include("peachjam.urls.generic_documents")),
    path("gazettes/", include("peachjam.urls.gazettes")),
    path("journals/", JournalListView.as_view(), name="journal_list"),
    path("judgments/", include("peachjam.urls.judgments")),
    path("legislation/", LegislationListView.as_view(), name="legislation_list"),
    path(
        "uncommenced-provisions/<int:pk>",
        UncommencedProvisionDetailView.as_view(),
        name="uncommenced_provision_detail",
    ),
    path(
        "unconstitutional-provisions/<int:pk>",
        UnconstitutionalProvisionDetailView.as_view(),
        name="unconstitutional_provision_detail",
    ),
    path(
        "document-uncommenced-provisions/<int:pk>",
        DocumentUncommencedProvisionListView.as_view(),
        name="document_uncommenced_provision_list",
    ),
    path(
        "uncommenced-provisions/",
        UncommencedProvisionListView.as_view(),
        name="uncommenced_provision_list",
    ),
    path(
        "unconstitutional-provisions/",
        UnconstitutionalProvisionListView.as_view(),
        name="unconstitutional_provision_list",
    ),
    path("taxonomy/", include("peachjam.urls.taxonomies")),
    # detail views
    path("authors/<slug:code>/", AuthorDetailView.as_view(), name="author"),
    path("place/<str:code>", PlaceDetailView.as_view(), name="place"),
    # documents
    path("", include("peachjam.urls.documents")),
    # general
    path("about/", AboutPageView.as_view(), name="about"),
    path(
        "pocketlaw-resources", PocketLawResources.as_view(), name="pocketlaw_resources"
    ),
    path("stats", MetabaseStatsView.as_view(), name="metabase_stats"),
    path("terms-of-use/", TermsOfUsePageView.as_view(), name="terms_of_use"),
    # admin
    path("admin/", include("peachjam.urls.admin")),
    path("comments/", include("peachjam.urls.comments")),
    # other apps
    path("search/", include(("peachjam_search.urls", "search"), namespace="search")),
    # user auth and account management
    path("accounts/", include("peachjam.urls.accounts")),
    # user-specific page fragments
    path(
        "me/",
        include(
            [
                path("saved-documents/", include("peachjam.urls.saved_documents")),
                path("follow/", include("peachjam.urls.following")),
            ]
        ),
    ),
    path("my/", include("peachjam.urls.my")),
]
