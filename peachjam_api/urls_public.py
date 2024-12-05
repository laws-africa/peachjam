from django.urls import include, path, re_path
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
    re_path(
        r"^judgments(?P<expression_frbr_uri>/akn/.*)/source.txt$",
        public_views.JudgmentsViewSet.as_view({"get": "source_txt"}),
        name="judgments-detail",
    ),
    re_path(
        r"^judgments(?P<expression_frbr_uri>/akn/.*)/source.pdf$",
        public_views.JudgmentsViewSet.as_view({"get": "source_pdf"}),
        name="judgments-detail",
    ),
    re_path(
        r"^judgments(?P<expression_frbr_uri>/akn/.*)$",
        public_views.JudgmentsViewSet.as_view({"get": "retrieve"}),
        name="judgments-detail",
    ),
]
