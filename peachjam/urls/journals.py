from django.urls import path

from peachjam.views import (
    JournalArticleListView,
    JournalArticleSlugDetailView,
    JournalListView,
    VolumeIssueDetailView,
    VolumeIssueListView,
)

urlpatterns = [
    path("", JournalListView.as_view(), name="journal_list"),
    path("articles/", JournalArticleListView.as_view(), name="journal_article_list"),
    path(
        "articles/<slug:slug>/",
        JournalArticleSlugDetailView.as_view(),
        name="journal_article_detail",
    ),
    path("<slug:slug>/", JournalArticleListView.as_view(), name="journal_detail"),
    path("<slug:slug>/volumes/", VolumeIssueListView.as_view(), name="volume_list"),
    path(
        "<slug:slug>/volumes/<slug:volume_slug>/",
        VolumeIssueDetailView.as_view(),
        name="volume_detail",
    ),
]
