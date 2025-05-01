from django.urls import include, path

from peachjam.views import (
    FolderCreateView,
    FolderDeleteView,
    FolderDownloadView,
    FolderListView,
    FolderUpdateView,
    MyHomeView,
    UserFollowingListView,
)

urlpatterns = [
    path("", MyHomeView.as_view(), name="my_home"),
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
