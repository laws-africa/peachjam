from django.urls import include, path

from africanlii import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    path(
        "legislation/", views.AGPLegislationListView.as_view(), name="legislation_list"
    ),
    path("", include("peachjam.urls")),
]
