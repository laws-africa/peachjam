from django.urls import include, path

from open_by_laws.views import HomePageView, MunicipalByLawsView
from open_by_laws.views.redirect import RedirectByLawView, RedirectOldPlaceCodesView

urlpatterns = [
    path("", HomePageView.as_view(), name="home_page"),
    path(
        "bylaws/<str:code>",
        MunicipalByLawsView.as_view(),
        name="municipal_by_laws",
    ),
    path(
        "bylaws/<str:code>/repealed",
        MunicipalByLawsView.as_view(variant="repealed"),
        name="municipal_by_laws_legislation_list_repealed",
    ),
    path(
        "bylaws/<str:code>/all",
        MunicipalByLawsView.as_view(variant="all"),
        name="municipal_by_laws_legislation_list_all",
    ),
    path(
        "za-<str:place_code>/<str:language_code>/",
        RedirectOldPlaceCodesView.as_view(),
        name="old_place_code_redirect",
    ),
    path(
        "za-<str:place_code>/act/by-law/<path:path>/<str:language>/",
        RedirectByLawView.as_view(),
        name="old_by_law_redirect",
    ),
    path("", include("liiweb.urls")),
]
