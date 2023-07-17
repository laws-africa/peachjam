from liiweb.views import HomePageView as LiiWebPageView
from peachjam.models import Locality


class HomePageView(LiiWebPageView):
    template_name = "open_by_laws/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        codes = "cpt eth jhb wc033 wc011 ec443 wc013 wc012 wc015 wc041 wc023".split()
        context["municipalities"] = Locality.objects.filter(code__in=codes)
        return context
