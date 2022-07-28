from django.urls import include, path

from lawlibrary import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    path("judgments/", views.FakeListView.as_view(), name="judgment_list"),
    path(
        "judgements/<int:court_id>/",
        views.FilteredListView.as_view(),
        name="court_list",
    ),
    path(
        "judgements/<int:court_id>/<int:yearselected>",
        views.FilteredListView.as_view(),
        name="year_court_list",
    ),
    path("", include("liiweb.urls")),
]
