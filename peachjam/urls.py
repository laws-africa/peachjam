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
from django.contrib.auth import views
from django.urls import include, path, re_path
from django.views.decorators.cache import cache_page

from africanlii.feeds import (
    CoreDocumentAtomSiteNewsFeed,
    GenericDocumentAtomSiteNewsFeed,
    JudgmentAtomSiteNewsFeed,
    LegalInstrumentAtomSiteNewsFeed,
    LegislationAtomSiteNewsFeed,
)
from peachjam.views import (
    AboutPageView,
    AuthorListView,
    DocumentDetailViewResolver,
    DocumentSourcePDFView,
    DocumentSourceView,
    GenericDocumentListView,
    HomePageView,
    JudgmentListView,
    LegalInstrumentListView,
    LegislationListView,
)

common_url_patterns = [
    path("search/", include(("peachjam_search.urls", "search"), namespace="search")),
    path(
        "admin/login/",
        views.LoginView.as_view(template_name="admin/login.html"),
        name="login",
    ),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("api/", include("peachjam_api.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
]

urlpatterns = common_url_patterns + [
    path("", HomePageView.as_view(), name="home_page"),
    path("judgments/", JudgmentListView.as_view(), name="judgment_list"),
    path("legislation/", LegislationListView.as_view(), name="legislation_list"),
    path(
        "legal_instruments/",
        LegalInstrumentListView.as_view(),
        name="legal_instrument_list",
    ),
    path(
        "about/",
        AboutPageView.as_view(),
        name="about",
    ),
    path(
        "generic_documents/",
        GenericDocumentListView.as_view(),
        name="generic_document_list",
    ),
    re_path(
        r"^(?P<frbr_uri>akn/.*)/source$",
        cache_page(60 * 60 * 24)(DocumentSourceView.as_view()),
        name="document_source",
    ),
    path(
        "authors/<int:pk>/",
        AuthorListView.as_view(),
        name="authors",
    ),
    re_path(
        r"^(?P<frbr_uri>akn/.*)/source.pdf$",
        cache_page(60 * 60 * 24)(DocumentSourcePDFView.as_view()),
        name="document_source_pdf",
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
    re_path(
        r"^(?P<frbr_uri>akn/.*)/$",
        DocumentDetailViewResolver.as_view(),
        name="document_detail",
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
