from django.views.generic import TemplateView


class TermsOfUsePageView(TemplateView):
    template_name = "peachjam/terms_of_use.html"
