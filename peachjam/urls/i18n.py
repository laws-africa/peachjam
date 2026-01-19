from django.urls import include, path, register_converter

from peachjam.helpers import ISODateConverter
from peachjam.views import (
    AboutPageView,
    AuthorDetailView,
    BookListView,
    HomePageView,
    JournalArticleSlugDetailView,
    PlaceDetailView,
    PocketLawResources,
    TermsOfUsePageView,
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
    path(
        "journal-articles/<slug:slug>/",
        JournalArticleSlugDetailView.as_view(),
        name="journal_article_detail",
    ),
    path("journals/", include("peachjam.urls.journals")),
    path("judgments/", include("peachjam.urls.judgments")),
    path("taxonomy/", include("peachjam.urls.taxonomies")),
    # detail views
    path("authors/<slug:code>/", AuthorDetailView.as_view(), name="author"),
    path("place/<str:code>", PlaceDetailView.as_view(), name="place"),
    # documents
    path("", include("peachjam.urls.legislation")),
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
    path("", include("peachjam_subs.urls")),
    # user-specific page fragments
    path("user/", include("peachjam.urls.user")),
    path("my/", include("peachjam.urls.my")),
]
