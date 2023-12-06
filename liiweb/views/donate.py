from django.views.generic import TemplateView


class DonatePageView(TemplateView):
    template_name = "liiweb/donate.html"
