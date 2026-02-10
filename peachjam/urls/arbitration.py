from django.urls import path

from peachjam.views import (
    ArbitralInstitutionDetailView,
    ArbitralInstitutionListView,
    ArbitrationAwardDetailView,
    ArbitrationAwardListView,
    ArbitrationHubPage,
)

urlpatterns = [
    path("", ArbitrationHubPage.as_view(), name="arbitration_hub"),
    path("awards/", ArbitrationAwardListView.as_view(), name="arbitration_award_list"),
    path(
        "awards/<path:case_number>/",
        ArbitrationAwardDetailView.as_view(),
        name="arbitration_award_detail",
    ),
    path(
        "institutions/",
        ArbitralInstitutionListView.as_view(),
        name="arbitral_institution_list",
    ),
    path(
        "institutions/<str:acronym>/",
        ArbitralInstitutionDetailView.as_view(),
        name="arbitral_institution_detail",
    ),
]
