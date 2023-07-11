from liiweb.views import HomePageView as LiiWebPageView


class HomePageView(LiiWebPageView):
    template_name = "open_by_laws/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["municipalities"] = [
            {"code": "cpt", "name": "Cape Town"},
            {"code": "eth", "name": "eThekwini"},
            {"code": "jhb", "name": "Johannesburg"},
            {
                "code": "wc033",
                "name": "Cape Agulhas",
            },
            {
                "code": "wc011",
                "name": "Matzikama",
            },
            {
                "code": "ec443",
                "name": "Mbizana",
            },
            {
                "code": "wc013",
                "name": "Bergrivier",
            },
            {
                "code": "wc012",
                "name": "Cederberg",
            },
            {"code": "wc015", "name": "Swartland"},
            {"code": "wc041", "name": "Kannaland"},
            {"code": "wc023", "name": "Drakenstein"},
        ]
        return context
