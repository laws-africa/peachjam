from django.urls import include, path
from rest_framework import routers

from . import views

router = routers.DefaultRouter()
router.register("documents", views.DocumentSearchViewSet, basename="document_search")
router.register("click", views.SearchClickViewSet, basename="search_click")

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path("api/", include(router.urls)),
    path(
        "api/saved-searches", views.SavedSearchCreateView.as_view(), name="saved_search"
    ),
    path("", views.SearchView.as_view(), name="search"),
    path("traces", views.SearchTraceListView.as_view(), name="search_traces"),
    path(
        "traces/<uuid:pk>", views.SearchTraceDetailView.as_view(), name="search_trace"
    ),
]
