from django.urls import include, path
from rest_framework import routers

from . import public_views

router = routers.DefaultRouter(trailing_slash=False)
router.register(
    r"judgments",
    public_views.JudgmentsViewSet,
    basename="judgments",
)
router.register(
    r"gazettes",
    public_views.GazettesViewSet,
    basename="gazettes",
)

urlpatterns = [
    # public-facing API
    path("v1/", include(router.urls)),
]
