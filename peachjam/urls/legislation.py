from django.urls import path

from peachjam.views import (
    DocumentUncommencedProvisionListView,
    LegislationListView,
    UncommencedProvisionDetailView,
    UncommencedProvisionListView,
    UnconstitutionalProvisionDetailView,
    UnconstitutionalProvisionListView,
)

urlpatterns = [
    path("legislation/", LegislationListView.as_view(), name="legislation_list"),
    path(
        "uncommenced-provisions/<int:pk>",
        UncommencedProvisionDetailView.as_view(),
        name="uncommenced_provision_detail",
    ),
    path(
        "unconstitutional-provisions/<int:pk>",
        UnconstitutionalProvisionDetailView.as_view(),
        name="unconstitutional_provision_detail",
    ),
    path(
        "document-uncommenced-provisions/<int:pk>",
        DocumentUncommencedProvisionListView.as_view(),
        name="document_uncommenced_provision_list",
    ),
    path(
        "uncommenced-provisions/",
        UncommencedProvisionListView.as_view(),
        name="uncommenced_provision_list",
    ),
    path(
        "unconstitutional-provisions/",
        UnconstitutionalProvisionListView.as_view(),
        name="unconstitutional_provision_list",
    ),
]
