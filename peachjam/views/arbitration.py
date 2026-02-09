from functools import cached_property

from django.shortcuts import get_object_or_404
from django.views.generic import ListView

from peachjam.models import ArbitralInstitution, ArbitrationAward
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class ArbitralInstitutionListView(ListView):
    template_name = "peachjam/arbitration/arbitral_institution_list.html"
    model = ArbitralInstitution
    context_object_name = "arbitral_institutions"


class ArbitrationAwardListView(FilteredDocumentListView):
    template_name = "peachjam/arbitration/arbitration_award_list.html"
    model = ArbitrationAward
    navbar_link = "arbitration"


@registry.register_doc_type("arbitration_award")
class ArbitrationAwardDetailView(BaseDocumentDetailView):
    model = ArbitrationAward
    slug_field = "case_number"
    slug_url_kwarg = "case_number"

    @cached_property
    def arbitration_award(self):
        return get_object_or_404(
            ArbitrationAward.objects.select_related(
                "institution",
                "seat",
                "claimants_country_of_origin",
                "respondents_county_of_origin",
                "rules_of_arbitration",
            ),
            case_number=self.kwargs.get("case_number"),
        )

    def get_object(self, *args, **kwargs):
        return self.arbitration_award
