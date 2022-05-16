from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from africanlii import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    path("", include("peachjam.urls")),
    # Judgments
    path("judgments/", views.JudgmentListView.as_view(), name="judgment_list"),
    path(
        "judgments/<int:pk>", views.JudgmentDetailView.as_view(), name="judgment_detail"
    ),
    # Legislation
    path("legislation/", views.LegislationListView.as_view(), name="legislation_list"),
    path(
        "legislation/<int:pk>",
        views.LegislationDetailView.as_view(),
        name="legislation_detail",
    ),
    # Legal Instruments
    path(
        "legal_instruments/",
        views.LegalInstrumentListView.as_view(),
        name="legal_instrument_list",
    ),
    path(
        "legal_instruments/<int:pk>",
        views.LegalInstrumentDetailView.as_view(),
        name="legal_instrument_detail",
    ),
    # Generic Documents
    path(
        "generic_documents/",
        views.GenericDocumentListView.as_view(),
        name="generic_document_list",
    ),
    path(
        "generic_documents/<int:pk>",
        views.GenericDocumentDetailView.as_view(),
        name="generic_document_detail",
    ),
    path(
        "documents/<int:pk>/source.pdf",
        views.DocumentSourceView.as_view(),
        name="document_source",
    ),
    path("topic/<slug:slug>/", views.TopicsView.as_view(), name="topic_list"),
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
