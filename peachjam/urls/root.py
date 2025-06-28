from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, register_converter

from peachjam.helpers import ISODateConverter
from peachjam.views import (
    AboutPageView,
    AuthorDetailView,
    BookListView,
    HomePageView,
    JournalListView,
    LegislationListView,
    PlaceDetailView,
    PocketLawResources,
    RobotsView,
    TermsOfUsePageView,
    UnconstitutionalProvisionListView,
)
from peachjam.views.generic_views import CSRFTokenView
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
        "unconstitutional-provisions/",
        UnconstitutionalProvisionListView.as_view(),
        name="unconstitutional_provision_list",
    ),
    path("taxonomy/", include("peachjam.urls.taxonomies")),
    path("feeds/", include("peachjam.urls.feeds")),
    # detail views
    path("authors/<slug:code>/", AuthorDetailView.as_view(), name="author"),
    path("place/<str:code>", PlaceDetailView.as_view(), name="place"),
    # documents
    path("", include("peachjam.urls.documents")),
    # user-related
    path("accounts/", include("peachjam.urls.accounts")),
    path("i18n/", include("peachjam.urls.i18n")),
    path("saved-documents/", include("peachjam.urls.saved_documents")),
    path("follow/", include("peachjam.urls.following")),
    path("my/", include("peachjam.urls.my")),
    # general
    path("_token", CSRFTokenView.as_view(), name="csrf_token"),
    path("about/", AboutPageView.as_view(), name="about"),
    path(
        "pocketlaw-resources", PocketLawResources.as_view(), name="pocketlaw_resources"
    ),
    path(
        "robots.txt",
        RobotsView.as_view(
            template_name="peachjam/robots.txt", content_type="text/plain"
        ),
    ),
    path("stats", MetabaseStatsView.as_view(), name="metabase_stats"),
    path("terms-of-use/", TermsOfUsePageView.as_view(), name="terms_of_use"),
    # offline documents
    path("", include("peachjam.urls.offline")),
    # admin
    path("admin/", include("peachjam.urls.admin")),
    path("comments/", include("peachjam.urls.comments")),
    # django-markdown-editor for admin area
    path("martor/", include("martor.urls")),
    # other apps
    path("search/", include(("peachjam_search.urls", "search"), namespace="search")),
    path("api/", include("peachjam_api.urls")),
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
