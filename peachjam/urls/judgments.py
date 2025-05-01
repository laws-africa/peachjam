from django.urls import path

from peachjam.views import (
    CourtClassDetailView,
    CourtClassMonthView,
    CourtClassYearView,
    CourtDetailView,
    CourtMonthView,
    CourtRegistryDetailView,
    CourtRegistryMonthView,
    CourtRegistryYearView,
    CourtYearView,
    JudgmentListView,
)

urlpatterns = [
    path("", JudgmentListView.as_view(), name="judgment_list"),
    path(
        "court-class/<str:court_class>/",
        CourtClassDetailView.as_view(),
        name="court_class",
    ),
    path(
        "court-class/<str:court_class>/<int:year>/",
        CourtClassYearView.as_view(),
        name="court_class_year",
    ),
    path(
        "court-class/<str:court_class>/<int:year>/<int:month>/",
        CourtClassMonthView.as_view(),
        name="court_class_month",
    ),
    path(
        "<str:code>/",
        CourtDetailView.as_view(),
        name="court",
    ),
    path(
        "<str:code>/<int:year>/",
        CourtYearView.as_view(),
        name="court_year",
    ),
    path(
        "<str:code>/<int:year>/<int:month>/",
        CourtMonthView.as_view(),
        name="court_month",
    ),
    path(
        "<str:code>/<str:registry_code>/",
        CourtRegistryDetailView.as_view(),
        name="court_registry",
    ),
    path(
        "<str:code>/<str:registry_code>/<int:year>/",
        CourtRegistryYearView.as_view(),
        name="court_registry_year",
    ),
    path(
        "<str:code>/<str:registry_code>/<int:year>/<int:month>/",
        CourtRegistryMonthView.as_view(),
        name="court_registry_month",
    ),
]
