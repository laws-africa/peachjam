from django.urls import include, path

from tanzlii import views

urlpatterns = [
    path("judgments/", views.JudgmentListView.as_view(), name="judgment_list"),
    path(
        "judgments/<str:code>/",
        views.CourtDetailView.as_view(),
        name="court",
    ),
    path(
        "judgments/<str:code>/<int:year>/",
        views.CourtYearView.as_view(),
        name="court_year",
    ),
    path(
        "judgments/<str:code>/<int:year>/<int:month>/",
        views.CourtMonthView.as_view(),
        name="court_month",
    ),
    path(
        "judgments/<str:code>/<str:registry_code>/",
        views.CourtRegistryDetailView.as_view(),
        name="court_registry",
    ),
    path(
        "judgments/<str:code>/<str:registry_code>/<int:year>/",
        views.CourtRegistryYearView.as_view(),
        name="court_registry_year",
    ),
    path(
        "judgments/<str:code>/<str:registry_code>/<int:year>/<int:month>/",
        views.CourtRegistryMonthView.as_view(),
        name="court_registry_month",
    ),
    path("", include("liiweb.urls")),
]
