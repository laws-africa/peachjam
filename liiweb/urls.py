from django.urls import include, path

from liiweb import views
from liiweb.views.donate import DonatePageView

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    path("pocketlaw", views.PocketlawView.as_view(), name="pocketlaw"),
    path(
        "legislation/",
        include(
            [
                path("", views.LegislationListView.as_view(), name="legislation_list"),
                path(
                    "repealed",
                    views.LegislationListView.as_view(variant="repealed"),
                    name="legislation_list_repealed",
                ),
                path(
                    "all",
                    views.LegislationListView.as_view(variant="all"),
                    name="legislation_list_all",
                ),
                path(
                    "subsidiary",
                    views.LegislationListView.as_view(variant="subleg"),
                    name="legislation_list_subsidiary",
                ),
                path(
                    "uncommenced",
                    views.LegislationListView.as_view(variant="uncommenced"),
                    name="legislation_list_uncommenced",
                ),
                path(
                    "recent",
                    views.LegislationListView.as_view(variant="recent"),
                    name="legislation_list_recent",
                ),
                path(
                    "localities",
                    views.LocalityLegislationView.as_view(),
                    name="locality_legislation",
                ),
                path(
                    "<str:code>/",
                    include(
                        [
                            path(
                                "",
                                views.LocalityLegislationListView.as_view(),
                                name="locality_legislation_list",
                            ),
                            path(
                                "all",
                                views.LocalityLegislationListView.as_view(
                                    variant="all"
                                ),
                                name="locality_legislation_list_all",
                            ),
                            path(
                                "subsidiary",
                                views.LocalityLegislationListView.as_view(
                                    variant="subleg"
                                ),
                                name="locality_legislation_list_subsidiary",
                            ),
                            path(
                                "uncommenced",
                                views.LocalityLegislationListView.as_view(
                                    variant="uncommenced"
                                ),
                                name="locality_legislation_list_uncommenced",
                            ),
                            path(
                                "recent",
                                views.LocalityLegislationListView.as_view(
                                    variant="recent"
                                ),
                                name="locality_legislation_list_recent",
                            ),
                            path(
                                "repealed",
                                views.LocalityLegislationListView.as_view(
                                    variant="repealed"
                                ),
                                name="locality_legislation_list_repealed",
                            ),
                        ]
                    ),
                ),
            ]
        ),
    ),
    path("donate/", DonatePageView.as_view(), name="donate"),
    path("", include("peachjam.urls")),
]
