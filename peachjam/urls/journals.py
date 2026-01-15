from django.urls import path

from peachjam.views import (
    JournalArticleListView,
    JournalListView,
    VolumeIssueDetailView,
    VolumeIssueListView,
)

urlpatterns = [
    path("journals/", JournalListView.as_view(), name="journal_list"),
    path(
        "journals/volumes/articles/",
        JournalArticleListView.as_view(),
        name="journal_article_list",
    ),
    path(
        "journals/volumes/",
        VolumeIssueListView.as_view(),
        name="volumes_list",
    ),
    path(
        "journals/volumes/<int:pk>/",
        VolumeIssueDetailView.as_view(),
        name="volume_detail",
    ),
]
