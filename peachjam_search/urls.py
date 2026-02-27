from django.urls import include, path
from rest_framework import routers

from . import views

router = routers.DefaultRouter()
router.register("click", views.SearchClickViewSet, basename="search_click")

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path("api/documents/", views.DocumentSearchView.as_view(), name="search_documents"),
    path(
        "api/documents/download",
        views.DocumentSearchView.as_view(action="download"),
        name="search_download",
    ),
    path(
        "api/documents/explain",
        views.DocumentSearchView.as_view(action="explain"),
        name="search_explain",
    ),
    path("api/documents/facets", views.DocumentSearchView.as_view(action="facets")),
    path("api/documents/suggest/", views.DocumentSearchView.as_view(action="suggest")),
    path("api/link-traces", views.LinkTracesView.as_view()),
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
    path("box", views.TemplateView.as_view(template_name="peachjam_search/box.html")),
    path("traces", views.SearchTraceListView.as_view(), name="search_traces"),
    path(
        "traces/<uuid:pk>", views.SearchTraceDetailView.as_view(), name="search_trace"
    ),
]
