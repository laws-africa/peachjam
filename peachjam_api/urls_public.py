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
router.register(
    r"ratifications",
    public_views.RatificationsViewSet,
    basename="ratifications",
)

urlpatterns = [
    # public-facing API
    path("", include(router.urls)),
    path(
        "judgments/<path:expression_frbr_uri>",
        public_views.JudgmentsViewSet.as_view({"get": "retrieve"}),
        name="judgments-detail",
    ),
]
