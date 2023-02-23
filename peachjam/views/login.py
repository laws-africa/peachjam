from allauth.socialaccount.models import SocialApp
from django.contrib.auth.views import LoginView


class PeachjamAdminLoginView(LoginView):
    template_name = "admin/login.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["social_apps"] = SocialApp.objects.all()
        return context
