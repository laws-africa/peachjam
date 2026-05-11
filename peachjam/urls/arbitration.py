from django.urls import path, re_path

from peachjam.views import (
    ArbitralInstitutionDetailView,
    ArbitralInstitutionListView,
    ArbitrationAwardListView,
    ArbitrationHubPage,
    ArbitrationJudgmentDetailView,
    ArbitrationJudgmentListView,
)

urlpatterns = [
    path("", ArbitrationHubPage.as_view(), name="arbitration_hub"),
    path("awards/", ArbitrationAwardListView.as_view(), name="arbitration_award_list"),
    path(
        "judgments/",
        ArbitrationJudgmentListView.as_view(),
        name="arbitration_judgment_list",
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
    re_path(
        r"^judgments/(?P<frbr_uri>akn/?.*)$",
        ArbitrationJudgmentDetailView.as_view(),
        name="arbitration_judgment_detail",
    ),
]
