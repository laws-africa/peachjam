from django.urls import include, path

from obl_microsites.views import RedirectHomeView

urlpatterns = [
    # redirect the homepage view to the appropriate municipality listing view
    path("", RedirectHomeView.as_view()),
    path("", include("open_by_laws.urls")),
]
