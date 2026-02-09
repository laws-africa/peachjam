from django.urls import path

from peachjam.views import (
    ArbitralInstitutionListView,
    ArbitrationAwardDetailView,
    ArbitrationAwardListView,
)

urlpatterns = [
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
]
