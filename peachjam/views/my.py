from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models.aggregates import Count
from django.views.generic.base import TemplateView

from peachjam.models import Folder


class MyHomeView(LoginRequiredMixin, TemplateView):
    template_name = "peachjam/my/home.html"
    tab = "my"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["folders"] = Folder.objects.filter(user=self.request.user).annotate(
            n_saved_documents=Count("saved_documents")
        )
        return context
