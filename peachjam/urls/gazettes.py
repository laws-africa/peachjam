from django.urls import path

from peachjam.views import GazetteListView, GazetteYearView

urlpatterns = [
    path("", GazetteListView.as_view(), name="gazettes"),
    path(
        "<str:code>/",
        GazetteListView.as_view(),
        name="gazettes_by_locality",
    ),
    path("<int:year>", GazetteYearView.as_view(), name="gazettes_by_year"),
    path(
        "<str:code>/<int:year>",
        GazetteYearView.as_view(),
        name="gazettes_by_year",
    ),
]
