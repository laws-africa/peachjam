from django.urls import path

from peachjam.views import (
    JournalArticleListView,
    JournalDetailView,
    JournalListView,
    VolumeIssueDetailView,
)

urlpatterns = [
    path("", JournalListView.as_view(), name="journal_list"),
    path("articles/", JournalArticleListView.as_view(), name="journal_article_list"),
    path("<slug:slug>/", JournalDetailView.as_view(), name="journal_detail"),
    path(
        "<slug:slug>/volumes/<slug:volume_slug>/",
        VolumeIssueDetailView.as_view(),
        name="volume_detail",
    ),
]
