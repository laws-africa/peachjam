from django.urls import include, path

from peachjam.views import (
    AccountView,
    DocumentAccessGroupDetailView,
    EditAccountView,
    LoggedOutView,
    NavbarMenuView,
)

urlpatterns = [
    path("", include("allauth.urls")),
    path("profile/", AccountView.as_view(), name="my_account"),
    path("profile/edit", EditAccountView.as_view(), name="edit_account"),
    path("logged-out", LoggedOutView.as_view(), name="account_logged_out"),
    path("navbar-menu", NavbarMenuView.as_view(), name="user_navbar_menu"),
    path(
        "document-access-groups/",
        include(
            [
                path(
                    "<int:pk>",
                    DocumentAccessGroupDetailView.as_view(),
                    name="document_access_group_detail",
                ),
            ]
        ),
    ),
]
