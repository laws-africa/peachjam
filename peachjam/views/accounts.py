from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views import View
from django.views.generic import UpdateView

from peachjam.forms import UserForm

User = get_user_model()


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
                "username": self.request.user.username,
            }
            response = JsonResponse(user_details)
            return response
        return HttpResponse(status=404)
