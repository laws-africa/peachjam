from django.urls import include, path
from django.views.generic import RedirectView

from lawlibrary import views

urlpatterns = [
    path(
        "legislation/",
        include(
            [
                path("localities", RedirectView.as_view(url="/legislation/provincial")),
                path(
                    "provincial",
                    views.LocalityLegislationView.as_view(variant="provincial"),
                    name="locality_legislation",
                ),
                path(
                    "municipal",
                    views.LocalityLegislationView.as_view(variant="municipal"),
                    name="municipal_legislation",
                ),
                path(
                    "<str:code>/",
                    views.LocalityLegislationListView.as_view(),
                    name="locality_legislation_list",
                ),
                path(
                    "<str:code>/repealed",
                    views.LocalityLegislationListView.as_view(variant="repealed"),
                    name="locality_legislation_list_repealed",
                ),
                path(
                    "<str:code>/subsidiary",
                    views.LocalityLegislationListView.as_view(variant="subleg"),
                    name="locality_legislation_list_subsidiary",
                ),
                path(
                    "<str:code>/all",
                    views.LocalityLegislationListView.as_view(variant="all"),
                    name="locality_legislation_list_all",
                ),
            ]
        ),
    ),
    path("", include("liiweb.urls")),
]
