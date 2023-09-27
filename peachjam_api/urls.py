from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework import routers

from . import views

router = routers.DefaultRouter()
router.register(r"relationships", views.RelationshipViewSet, basename="relationships")
router.register(r"works", views.WorksViewSet, basename="works")
router.register(r"citation-links", views.CitationLinkViewSet, basename="citation-links")

urlpatterns = [
    # internal API
    path("", include(router.urls)),
    # semi-public
    path(
        "v1/ingestors/<int:ingestor_id>/webhook",
        views.IngestorWebhookView.as_view(),
        name="ingestor_webhook",
    ),
    # public-facing API
    path("v1/", include("peachjam_api.urls_public")),
    # schema browsing
    path(
        "v1/schema",
        SpectacularAPIView.as_view(urlconf="peachjam_api.urls_public"),
        name="schema",
    ),
    path(
        "v1/schema/swagger-ui",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "v1/schema/redoc", SpectacularRedocView.as_view(url_name="schema"), name="redoc"
    ),
    path(
        "check-duplicates/",
        views.CheckDuplicatesView.as_view(),
        name="check_duplicates",
    ),
]
