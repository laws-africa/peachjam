from django.views.generic import TemplateView


class HomePageView(TemplateView):
    template_name = "liiweb/home.html"


class PocketlawView(TemplateView):
    template_name = "liiweb/pocketlaw.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(pocketlaw_version="1.0.6", **kwargs)
