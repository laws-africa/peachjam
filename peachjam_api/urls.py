from django.urls import include, path
from rest_framework import routers

from . import public_views, views

internal_router = routers.DefaultRouter()
internal_router.register(
    r"relationships", views.RelationshipViewSet, basename="relationships"
)
internal_router.register(r"works", views.WorksViewSet, basename="works")
internal_router.register(
    r"citation-links", views.CitationLinkViewSet, basename="citation-links"
)

public_router = routers.DefaultRouter(trailing_slash=False)
public_router.register(
    r"judgments", public_views.JudgmentsViewSet, basename="judgments"
)

urlpatterns = [
    # internal API
    path("", include(internal_router.urls)),
    # public-facing API
    path("v1/", include(public_router.urls)),
    path(
        "v1/ingestors/<int:ingestor_id>/webhook",
        views.IngestorWebhookView.as_view(),
        name="ingestor_webhook",
    ),
]
