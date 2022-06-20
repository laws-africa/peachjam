from django.urls import include, path
from rest_framework import routers

from . import views

router = routers.DefaultRouter()
router.register(r"relationships", views.RelationshipViewSet, basename="relationships")
router.register(r"works", views.WorksViewSet, basename="works")

urlpatterns = [
    path("", include(router.urls)),
]
