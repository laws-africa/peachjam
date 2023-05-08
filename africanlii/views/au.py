from countries_plus.models import Country
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, TemplateView

from africanlii.models import RatificationCountry
from peachjam.models import AfricanUnionOrgan, MemberState, RegionalEconomicCommunity
from peachjam.views import AuthorDetailView, PlaceDetailView


class AfricanUnionDetailPageView(TemplateView):
    template_name = "peachjam/au_detail_page.html"
    model = AfricanUnionOrgan
    navbar_link = "au"

    def get_queryset(self):
        return self.model.objects.prefetch_related("author")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["au_organs"] = self.get_queryset()
        context["recs"] = RegionalEconomicCommunity.objects.prefetch_related("locality")
        context["member_states"] = MemberState.objects.prefetch_related("country")
        return context


class AfricanUnionOrganDetailView(AuthorDetailView):
    template_name = "peachjam/au_organ_detail.html"


class RegionalEconomicCommunityDetailView(PlaceDetailView):
    template_name = "peachjam/regional_economic_community_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["rec"] = get_object_or_404(
            RegionalEconomicCommunity, locality=self.locality
        )
        return context


class MemberStateDetailView(DetailView):
    template_name = "peachjam/member_state_detail.html"
    model = MemberState
    slug_url_kwarg = "country"
    slug_field = "country"

    def get(self, request, *args, **kwargs):
        self.country = get_object_or_404(Country, iso=kwargs["country"])
        self.member_state = get_object_or_404(self.model.objects, country=self.country)
        self.ratification_countries = RatificationCountry.objects.prefetch_related(
            "ratification", "country"
        ).filter(country=self.country)

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            **kwargs,
            member_state=self.member_state,
            ratification_countries=self.ratification_countries,
            doc_count=self.ratification_countries.count()
        )
