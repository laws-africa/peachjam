from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views import View
from django.views.generic import UpdateView
from django.views.generic.base import TemplateView

from peachjam.auth import user_display
from peachjam.forms import UserForm

User = get_user_model()


class AccountsHomeView(LoginRequiredMixin, TemplateView):
    template_name = "user_account/home.html"


class EditAccountView(LoginRequiredMixin, UpdateView):
    authentication_required = True
    model = User
    template_name = "user_account/edit.html"
    form_class = UserForm

    def get_success_url(self):
        return reverse("edit_account")

    def get_object(self, queryset=None):
        return self.request.user


class GetAccountView(View):
    def get_object(self):
        return self.request.user

    def get(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            user_details = {
                "id": self.request.user.id,
                "email": self.request.user.email,
                "name": user_display(self.request.user),
            }
            response = JsonResponse(user_details)
            return response
        return HttpResponse(status=404)
