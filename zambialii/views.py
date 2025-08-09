from django.shortcuts import get_object_or_404
from django.views.generic.base import TemplateView

from peachjam.models import Taxonomy


class ParalegalsView(TemplateView):
    template_name = "zambialii/paralegals.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["taxonomy"] = get_object_or_404(Taxonomy.objects, slug="paralegals")

        return context
