from django.urls import path

from peachjam.views import (
    ArticleAttachmentDetailView,
    ArticleAuthorDetailView,
    ArticleAuthorYearDetailView,
    ArticleDetailView,
    ArticleEditButtonView,
    ArticleListView,
    ArticleTopicView,
    ArticleTopicYearView,
    ArticleYearView,
)

urlpatterns = [
    path("", ArticleListView.as_view(), name="article_list"),
    path(
        "authors/<username>",
        ArticleAuthorDetailView.as_view(),
        name="article_author",
    ),
    path(
        "authors/<username>/<int:year>",
        ArticleAuthorYearDetailView.as_view(),
        name="article_author_year",
    ),
    path(
        "<int:year>",
        ArticleYearView.as_view(),
        name="article_year_archive",
    ),
    path(
        "<slug:topic>",
        ArticleTopicView.as_view(),
        name="article_topic",
    ),
    path(
        "<slug:topic>/<int:year>",
        ArticleTopicYearView.as_view(),
        name="article_topic_year",
    ),
    path(
        "<isodate:date>/<str:author>/<slug:slug>",
        ArticleDetailView.as_view(),
        name="article_detail",
    ),
    path(
        "<int:pk>/edit-button",
        ArticleEditButtonView.as_view(),
        name="article_edit_button",
    ),
    path(
        "<isodate:date>/<str:author>/<slug:slug>/attachment/<int:pk>/<str:filename>",
        ArticleAttachmentDetailView.as_view(),
        name="article_attachment",
    ),
]
