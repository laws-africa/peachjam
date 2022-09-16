from django.urls import include, path

from lawlibrary import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    path("judgments/", views.JudgmentListView.as_view(), name="judgment_list"),
    path("judgments/<str:code>/", views.CourtDetailView.as_view(), name="court_detail"),
    path(
        "judgments/<str:code>/<int:year>/",
        views.CourtYearView.as_view(),
        name="court_year",
    ),
    path("legislation/", views.LegislationListView.as_view(), name="legislation_list"),
    path(
        "legislation/provincial",
        views.ProvincialLegislationView.as_view(),
        name="provincial_legislation",
    ),
    path(
        "legislation/repealed",
        views.LegislationListView.as_view(variant="repealed"),
        name="legislation_list_repealed",
    ),
    path(
        "legislation/all",
        views.LegislationListView.as_view(variant="all"),
        name="legislation_list_all",
    ),
    path(
        "legislation/<str:code>/",
        views.ProvincialLegislationListView.as_view(),
        name="provincial_legislation_list",
    ),
    path(
        "legislation/<str:code>/repealed",
        views.ProvincialLegislationListView.as_view(variant="repealed"),
        name="provincial_legislation_list_repealed",
    ),
    path(
        "legislation/<str:code>/all",
        views.ProvincialLegislationListView.as_view(variant="all"),
        name="provincial_legislation_list_all",
    ),
    path("articles/", views.ArticleListView.as_view(), name="article_list"),
    path(
        "articles/<slug:slug>/",
        views.ArticleDetailView.as_view(),
        name="article_detail",
    ),
    path("", include("liiweb.urls")),
]
