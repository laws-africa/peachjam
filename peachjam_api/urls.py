from django.urls import include, path
from rest_framework import routers

from . import views

router = routers.DefaultRouter()
router.register(r"relationships", views.RelationshipViewSet, basename="relationships")
router.register(r"works", views.WorksViewSet, basename="works")
router.register(r"documents", views.CitationLinkViewSet, basename="citation-links")

urlpatterns = [
    path("", include(router.urls)),
]
