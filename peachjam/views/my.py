from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import TemplateView


class MyHomeView(LoginRequiredMixin, TemplateView):
    template_name = "peachjam/my/home.html"
    tab = "my"
