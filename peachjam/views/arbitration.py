from functools import cached_property

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, TemplateView

from peachjam.helpers import add_slash, get_language
from peachjam.models import ArbitralInstitution, ArbitrationAward
from peachjam.models.core_document import CoreDocument
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class ArbitrationHubPage(TemplateView):
    template_name = "peachjam/arbitration/arbitration_hub.html"


class ArbitralInstitutionListView(ListView):
    template_name = "peachjam/arbitration/arbitral_institution_list.html"
    model = ArbitralInstitution
    context_object_name = "arbitral_institutions"


class ArbitralInstitutionDetailView(FilteredDocumentListView):
    template_name = "peachjam/arbitration/arbitral_institution_detail.html"
    model = ArbitrationAward
    navbar_link = "arbitration"

    @cached_property
    def arbitral_institution(self):
        return get_object_or_404(
            ArbitralInstitution,
            acronym=self.kwargs.get("acronym"),
        )

    def get_base_queryset(self, exclude=None):
        return (
            super()
            .get_base_queryset(exclude=exclude)
            .filter(institution=self.arbitral_institution)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["arbitral_institution"] = self.arbitral_institution
        context["entity_profile"] = self.arbitral_institution.entity_profile.first()
        context["entity_profile_title"] = self.arbitral_institution.name
        context["hide_follow_button"] = True
        return context


class ArbitrationAwardListView(FilteredDocumentListView):
    template_name = "peachjam/arbitration/arbitration_award_list.html"
    model = ArbitrationAward
    navbar_link = "arbitration"


@registry.register_doc_type("arbitration_award")
class ArbitrationAwardDetailView(BaseDocumentDetailView):
    model = ArbitrationAward
    template_name = "peachjam/arbitration/arbitration_award_detail.html"

    @cached_property
    def arbitration_award(self):
        frbr_uri = add_slash(self.kwargs.get("frbr_uri"))
        obj, _exact = CoreDocument.objects.best_for_frbr_uri(
            frbr_uri, get_language(self.request)
        )
        if not obj or not isinstance(obj, ArbitrationAward):
            raise Http404()
        if not obj.published:
            raise Http404()
        return ArbitrationAward.objects.select_related(
            "institution",
            "seat",
            "claimants_country_of_origin",
            "respondents_country_of_origin",
            "rules_of_arbitration",
        ).get(pk=obj.pk)

    def get_object(self, *args, **kwargs):
        return self.arbitration_award
