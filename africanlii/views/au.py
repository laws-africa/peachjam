from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, TemplateView

from africanlii.models import AfricanUnionOrgan, MemberState, RegionalEconomicCommunity
from peachjam.views import AuthorDetailView


class AfricanUnionDetailPageView(TemplateView):
    template_name = "peachjam/au_detail_page.html"
    model = AfricanUnionOrgan

    def get_queryset(self):
        return self.model.objects.prefetch_related("author")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["au_organs"] = self.get_queryset()
        context["recs"] = RegionalEconomicCommunity.objects.prefetch_related("locality")
        return context


class BaseDetailView(DetailView):
    template_name = None
    model = None

    def get(self, request, *args, **kwargs):
        self.obj = get_object_or_404(self.model, pk=kwargs["pk"])
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["obj"] = self.obj
        return context


class AfricanUnionOrganDetailView(AuthorDetailView):
    template_name = "peachjam/au_organ_detail.html"


class RegionalEconomicCommunityDetailView(BaseDetailView):
    template_name = "peachjam/regional_economic_community_detail.html"
    model = RegionalEconomicCommunity


class MemberStateDetailView(BaseDetailView):
    template_name = "peachjam/member_state_detail.html"
    model = MemberState
