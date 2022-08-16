from django.urls import include, path

from lawlibrary import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    path("judgments/", views.JudgmentListView.as_view(), name="judgment_list"),
    path("judgments/<str:code>/", views.CourtDetailView.as_view(), name="court_detail"),
    path(
        "judgments/<str:code>/<int:year>/",
        views.CourtYearView.as_view(),
        name="court_year",
    ),
    path("legislation/", views.LegislationListView.as_view(), name="legislation_list"),
    path("", include("liiweb.urls")),
]
