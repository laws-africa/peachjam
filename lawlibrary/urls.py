from django.urls import include, path

from lawlibrary import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    path("judgments/", views.JudgmentListView.as_view(), name="judgment_list"),
    path("court/<int:pk>/", views.CourtDetailView.as_view(), name="court_detail"),
    path("", include("liiweb.urls")),
]
