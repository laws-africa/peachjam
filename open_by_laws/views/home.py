from liiweb.views import HomePageView as LiiWebPageView
from peachjam.models import Locality


class HomePageView(LiiWebPageView):
    template_name = "open_by_laws/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        codes = "cpt eth jhb wc015 wc041 wc023".split()
        context["municipalities"] = Locality.objects.filter(code__in=codes)
        context["official_municipal_partners"] = [
            {
                "name": "Bergrivier",
                "code": "za-wc013",
                "url": "https://bergrivier.openbylaws.org.za",
            },
            {
                "name": "Cape Agulhas",
                "code": "za-wc033",
                "url": "https://capeagulhas.openbylaws.org.za",
            },
            {
                "name": "Cederberg",
                "code": "za-wc012",
                "url": "https://cederberg.openbylaws.org.za",
            },
            {
                "name": "Matzikama",
                "code": "za-wc011",
                "url": "https://matzikama.openbylaws.org.za",
            },
            {
                "name": "Mbizana",
                "code": "za-ec443",
                "url": "https://mbizana.openbylaws.org.za",
            },
        ]

        return context
