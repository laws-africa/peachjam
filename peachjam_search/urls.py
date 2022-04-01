from django.urls import include
from django.urls import path
from rest_framework import routers

from . import views


router = routers.DefaultRouter()
router.register(r"judgments", views.JudgmentSearchViewSet, basename="judgment_search")

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path("api/", include(router.urls)),
    path("", views.SearchView.as_view(), name="search"),
]
