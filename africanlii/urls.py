from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from africanlii import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    path("", include("peachjam.urls")),
    path(
        "documents<path:expression_frbr_uri>/",
        views.DocumentDetailViewResolver.as_view(),
        name="document_detail",
    ),
    path(
        "documents<path:expression_frbr_uri>/source.pdf",
        views.DocumentSourceView.as_view(),
        name="document_source",
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
