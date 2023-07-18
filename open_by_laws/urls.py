from django.urls import include, path, re_path

from open_by_laws.views import HomePageView, MunicipalByLawsView
from open_by_laws.views.redirect import RedirectOldPlaceCodesView

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
    # This redirects old place codes to new place codes
    re_path(
        r"^(?P<country_code>\w{2})-(?P<place_code>\w+)/(?P<language_code>\w+)/$",
        RedirectOldPlaceCodesView.as_view(),
        name="old_place_code_redirect",
    ),
    path("", include("liiweb.urls")),
]
