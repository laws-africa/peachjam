from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models.aggregates import Count
from django.http.response import Http404
from django.views.generic.base import TemplateView

from peachjam.models import Folder, UserFollowing, pj_settings


class MyHomeView(LoginRequiredMixin, TemplateView):
    template_name = "peachjam/my/home.html"
    tab = "my"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["folders"] = Folder.objects.filter(user=self.request.user).annotate(
            n_saved_documents=Count("saved_documents")
        )
        context["doc_suggestions"] = list(
            UserFollowing.latest_documents_for_user(self.request.user, 10)
        )
        return context


class MyFrontpageView(TemplateView):
    """The My LII part of the site homepage that is loaded dynamically."""

    def get(self, request, *args, **kwargs):
        if not pj_settings().allow_signups:
            return Http404()
        return super().get(request, *args, **kwargs)

    def get_template_names(self):
        if self.request.user.is_authenticated:
            return ["peachjam/my/_frontpage.html"]
        return ["peachjam/my/_frontpage_anon.html"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context["folders"] = Folder.objects.filter(user=self.request.user).annotate(
                n_saved_documents=Count("saved_documents")
            )
            context["doc_suggestions"] = list(
                UserFollowing.latest_documents_for_user(self.request.user, 10)
            )
        return context
