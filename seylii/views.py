from django.views.generic import TemplateView


class DonatePageView(TemplateView):
    template_name = "seylii/donate.html"
