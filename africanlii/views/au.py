from django.views.generic import TemplateView

from africanlii.models import AfricanUnionOrgan, RegionalEconomicCommunity


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
