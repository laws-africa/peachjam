from django.urls import include, path

from peachjam.views import (
    DocumentAccessGroupDetailView,
    DocumentAccessGroupListView,
    EditAccountView,
    GetAccountView,
    LoggedOutView,
)

urlpatterns = [
    path("", include("allauth.urls")),
    path("profile/", EditAccountView.as_view(), name="edit_account"),
    path("user/", GetAccountView.as_view(), name="get_account"),
    path("logged-out", LoggedOutView.as_view(), name="account_logged_out"),
    path(
        "document-access-groups/",
        include(
            [
                path(
                    "",
                    DocumentAccessGroupListView.as_view(),
                    name="document_access_group_list",
                ),
                path(
                    "<int:pk>",
                    DocumentAccessGroupDetailView.as_view(),
                    name="document_access_group_detail",
                ),
            ]
        ),
    ),
]
