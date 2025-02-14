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
        "saved-searches/button",
        views.SavedSearchButtonView.as_view(),
        name="saved_search_button",
    ),
    path(
        "saved-searches/create",
        views.SavedSearchCreateView.as_view(),
        name="saved_search_create",
    ),
    path(
        "saved-searches/<int:pk>/update",
        views.SavedSearchUpdateView.as_view(),
        name="saved_search_update",
    ),
    path(
        "saved-searches/<int:pk>/delete",
        views.SavedSearchDeleteView.as_view(),
        name="saved_search_delete",
    ),
    path(
        "saved-searches/",
        views.SavedSearchListView.as_view(),
        name="saved_search_list",
    ),
    path(
        "feedback/create",
        views.SearchFeedbackCreateView.as_view(),
        name="search_feedback_create",
    ),
    path("", views.SearchView.as_view(), name="search"),
    path("traces", views.SearchTraceListView.as_view(), name="search_traces"),
    path(
        "traces/<uuid:pk>", views.SearchTraceDetailView.as_view(), name="search_trace"
    ),
]
