from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, TemplateView

from africanlii.constants import LIIS
from africanlii.models import (
    AfricanUnionInstitution,
    AfricanUnionOrgan,
    MemberState,
    RegionalEconomicCommunity,
)
from peachjam.models import CourtClass, RatificationCountry
from peachjam.views import AuthorDetailView, CoreDocument, PlaceDetailView


class AfricanUnionDetailPageView(TemplateView):
    template_name = "africanlii/au_detail_page.html"
    model = AfricanUnionOrgan
    navbar_link = "au"

    def get_queryset(self):
        return self.model.objects.prefetch_related("author")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["au_organs"] = self.get_queryset()
        context["recs"] = RegionalEconomicCommunity.objects.prefetch_related("locality")
        context["member_states"] = MemberState.objects.prefetch_related("country")
        context["au_institutions"] = AfricanUnionInstitution.objects.prefetch_related(
            "author"
        )
        context["court_classes"] = CourtClass.objects.prefetch_related("courts")
        context["liis"] = LIIS
        return context


class AfricanUnionOrganDetailView(AuthorDetailView):
    template_name = "africanlii/au_organ_detail.html"


class AfricanUnionInstitutionDetailView(AuthorDetailView):
    template_name = "africanlii/au_institution_detail.html"


class RegionalEconomicCommunityDetailView(PlaceDetailView):
    template_name = "africanlii/regional_economic_community_detail.html"
    queryset = CoreDocument.objects.prefetch_related("labels")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["doc_table_show_jurisdiction"] = False
        context["rec"] = get_object_or_404(
            RegionalEconomicCommunity, locality=self.locality
        )
        return context


class MemberStateDetailView(DetailView):
    template_name = "africanlii/member_state_detail.html"
    queryset = MemberState.objects.prefetch_related("country")
    slug_url_kwarg = "country"
    slug_field = "country"
    context_object_name = "member_state"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["ratification_countries"] = ratification_countries = (
            RatificationCountry.objects.prefetch_related("ratification", "country")
            .filter(country=self.get_object().country)
            .order_by("ratification__work__title")
        )
        context["doc_count"] = ratification_countries.count()
        context["liis"] = LIIS

        return context
