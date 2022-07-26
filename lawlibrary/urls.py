from django.urls import include, path

from lawlibrary import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    path("judgments/", views.JudgmentListView.as_view(), name="judgment_list"),
    path("", include("liiweb.urls")),
]
