from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models.aggregates import Count
from django.http.response import Http404
from django.views.generic.base import TemplateView

from peachjam.models import Folder, pj_settings
from peachjam.views.user_following import get_user_following_timeline


class CommonContextMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.user.is_authenticated:
            context["folders"] = Folder.objects.filter(user=self.request.user).annotate(
                n_saved_documents=Count("saved_documents")
            )
            context["following_timeline"] = get_user_following_timeline(
                self.request.user, 7, 15
            )

        return context


class MyHomeView(LoginRequiredMixin, CommonContextMixin, TemplateView):
    template_name = "peachjam/my/home.html"
    tab = "my"


class MyFrontpageView(CommonContextMixin, TemplateView):
    """The My LII part of the site homepage that is loaded dynamically."""

    def get(self, request, *args, **kwargs):
        if not pj_settings().allow_signups:
            return Http404()
        return super().get(request, *args, **kwargs)

    def get_template_names(self):
        if self.request.user.is_authenticated:
            return ["peachjam/my/_frontpage.html"]
        return ["peachjam/my/_frontpage_anon.html"]
