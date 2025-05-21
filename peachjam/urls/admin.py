from django.contrib import admin
from django.urls import path

from peachjam.views import (
    CheckDuplicateFilesView,
    DocumentAnonymiseAPIView,
    DocumentAnonymiseSuggestionsAPIView,
    DocumentAnonymiseView,
    JudgesAutocomplete,
    JudgmentWorksAutocomplete,
    PeachjamAdminLoginView,
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
    path("anon/<int:pk>", DocumentAnonymiseView.as_view(), name="anon"),
    path("anon/<int:pk>/update", DocumentAnonymiseAPIView.as_view()),
    path(
        "anon/<int:pk>/suggestions",
        DocumentAnonymiseSuggestionsAPIView.as_view(),
    ),
    path("check-duplicate-file", CheckDuplicateFilesView.as_view()),
    path("", admin.site.urls),
]
