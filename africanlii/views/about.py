from django.views.generic import TemplateView

from peachjam.views import AuthedViewMixin


class AboutPageView(AuthedViewMixin, TemplateView):
    template_name = "africanlii/about.html"
