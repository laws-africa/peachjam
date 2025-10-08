from django.urls import include, path

from peachjam.views import (
    AcceptTermsView,
    AccountView,
    DocumentAccessGroupDetailView,
    EditAccountView,
    LoggedOutView,
)

urlpatterns = [
    path("", include("allauth.urls")),
    path("accept-terms/", AcceptTermsView.as_view(), name="account_accept_terms"),
    path("profile/", AccountView.as_view(), name="my_account"),
    path("profile/edit", EditAccountView.as_view(), name="edit_account"),
    path("logged-out", LoggedOutView.as_view(), name="account_logged_out"),
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
