from allauth.socialaccount.models import SocialApp
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.views import LoginView
from django.views.generic import TemplateView


class AuthedViewMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """View mixin for views that require authentication and permissions (ie. most views)."""

    permission_required = []

    def get_permission_required(self):
        perms = super().get_permission_required()
        return list(perms)


class PeachjamAdminLoginView(LoginView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["social_accounts"] = SocialApp.objects.all()
        return context


class HomePageView(TemplateView):
    template_name = "peachjam/home.html"
