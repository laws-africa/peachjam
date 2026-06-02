from django.conf import settings

from liiweb.views import HomePageView as LiiWebPageView
from peachjam.models import Locality


class HomePageView(LiiWebPageView):
    template_name = "open_by_laws/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        codes = "cpt ec443 eth jhb wc011 wc013 wc015 wc023 wc033 wc041".split()
        context["municipalities"] = Locality.objects.filter(code__in=codes)
        context["microsites"] = settings.MICROSITES.values()

        return context
