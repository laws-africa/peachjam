from django.views.generic import TemplateView


class AboutPageView(TemplateView):
    template_name = "peachjam/about.html"
    navbar_link = "about"
