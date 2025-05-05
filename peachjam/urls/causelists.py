from django.urls import path

from peachjam.views import (
    CauseListCourtClassMonthView,
    CauseListCourtClassView,
    CauseListCourtClassYearView,
    CauseListCourtDetailView,
    CauseListCourtMonthView,
    CauseListCourtRegistryDetailView,
    CauseListCourtRegistryMonthView,
    CauseListCourtRegistryYearView,
    CauseListCourtYearView,
    CauseListListView,
)

urlpatterns = [
    path("", CauseListListView.as_view(), name="causelist_list"),
    path(
        "<str:code>/",
        CauseListCourtDetailView.as_view(),
        name="causelist_court",
    ),
    path(
        "court-class/<str:court_class>/",
        CauseListCourtClassView.as_view(),
        name="causelist_court_class",
    ),
    path(
        "court-class/<str:court_class>/<int:year>/",
        CauseListCourtClassYearView.as_view(),
        name="causelist_court_class_year",
    ),
    path(
        "court-class/<str:court_class>/<int:year>/<int:month>/",
        CauseListCourtClassMonthView.as_view(),
        name="causelist_court_class_month",
    ),
    path(
        "<str:code>/<int:year>/",
        CauseListCourtYearView.as_view(),
        name="causelist_court_year",
    ),
    path(
        "<str:code>/<int:year>/<int:month>/",
        CauseListCourtMonthView.as_view(),
        name="causelist_court_month",
    ),
    path(
        "<str:code>/<str:registry_code>/",
        CauseListCourtRegistryDetailView.as_view(),
        name="causelist_court_registry",
    ),
    path(
        "<str:code>/<str:registry_code>/<int:year>/",
        CauseListCourtRegistryYearView.as_view(),
        name="causelist_court_registry_year",
    ),
    path(
        "<str:code>/<str:registry_code>/<int:year>/<int:month>/",
        CauseListCourtRegistryMonthView.as_view(),
        name="causelist_court_registry_month",
    ),
]
