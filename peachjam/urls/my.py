from django.urls import include, path

from peachjam.views import (
    FolderCreateView,
    FolderDeleteView,
    FolderDownloadView,
    FolderListView,
    FolderUpdateView,
    MyFrontpageView,
    MyHomeView,
    MyTimelineView,
    UserFollowingListView,
)

urlpatterns = [
    path("", MyHomeView.as_view(), name="my_home"),
    path("timeline", MyTimelineView.as_view(), name="my_timeline"),
    path("frontpage", MyFrontpageView.as_view(), name="my_frontpage"),
    path(
        "folders/",
        include(
            [
                path(
                    "",
                    FolderListView.as_view(),
                    name="folder_list",
                ),
                path(
                    "create",
                    FolderCreateView.as_view(),
                    name="folder_create",
                ),
                path(
                    "<int:pk>/update",
                    FolderUpdateView.as_view(),
                    name="folder_update",
                ),
                path(
                    "<int:pk>/delete",
                    FolderDeleteView.as_view(),
                    name="folder_delete",
                ),
                path(
                    "<int:pk>/download",
                    FolderDownloadView.as_view(),
                    name="folder_download",
                ),
            ]
        ),
    ),
    path("following/", UserFollowingListView.as_view(), name="user_following_list"),
]
