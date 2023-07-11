from django.urls import include, path

from open_by_laws.views import HomePageView, MunicipalByLawsView

urlpatterns = [
    path("", HomePageView.as_view(), name="home_page"),
    path(
        "municipal-by-laws/<str:code>",
        MunicipalByLawsView.as_view(),
        name="municipal_by_laws",
    ),
    path(
        "municipal-by-laws/<str:code>/repealed",
        MunicipalByLawsView.as_view(variant="repealed"),
        name="municipal_by_laws_legislation_list_repealed",
    ),
    path(
        "municipal-by-laws/<str:code>/all",
        MunicipalByLawsView.as_view(variant="all"),
        name="municipal_by_laws_legislation_list_all",
    ),
    path("", include("liiweb.urls")),
]
