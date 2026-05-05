from django.contrib import admin
from django.urls import path

from peachjam.views import (
    CheckDuplicateFilesView,
    DocumentAnonymiseAPIView,
    DocumentAnonymiseSuggestionsAPIView,
    DocumentAnonymiseView,
    FlynoteManagerDetailView,
    FlynoteManagerSearchView,
    FlynoteManagerTreeChildrenView,
    FlynoteManagerTreeView,
    FlynoteManagerView,
    JudgesAutocomplete,
    JudgmentWorksAutocomplete,
    PeachjamAdminLoginView,
    VolumeIssueAutocomplete,
    WorkAutocomplete,
)

urlpatterns = [
    path(
        "login/",
        PeachjamAdminLoginView.as_view(),
        name="login",
    ),
    # autocomplete for admin area
    path(
        "autocomplete/works",
        WorkAutocomplete.as_view(),
        name="autocomplete-works",
    ),
    path(
        "autocomplete/judges",
        JudgesAutocomplete.as_view(),
        name="autocomplete-judges",
    ),
    path(
        "autocomplete/judgments",
        JudgmentWorksAutocomplete.as_view(),
        name="autocomplete-judgment-works",
    ),
    path(
        "autocomplete/volume-issues",
        VolumeIssueAutocomplete.as_view(),
        name="autocomplete-volume-issues",
    ),
    path("anon/<int:pk>", DocumentAnonymiseView.as_view(), name="anon"),
    path("anon/<int:pk>/update", DocumentAnonymiseAPIView.as_view()),
    path(
        "anon/<int:pk>/suggestions",
        DocumentAnonymiseSuggestionsAPIView.as_view(),
    ),
    path("check-duplicate-file", CheckDuplicateFilesView.as_view()),
    path(
        "flynote-manager/tree/",
        FlynoteManagerTreeView.as_view(),
        name="flynote-manager-tree",
    ),
    path(
        "flynote-manager/tree/<int:pk>/children/",
        FlynoteManagerTreeChildrenView.as_view(),
        name="flynote-manager-tree-children",
    ),
    path(
        "flynote-manager/workspace/search/",
        FlynoteManagerSearchView.as_view(),
        name="flynote-manager-search",
    ),
    path(
        "flynote-manager/workspace/<int:pk>/",
        FlynoteManagerDetailView.as_view(),
        name="flynote-manager-detail",
    ),
    path("flynote-manager/", FlynoteManagerView.as_view(), name="flynote-manager"),
    path("", admin.site.urls),
]
