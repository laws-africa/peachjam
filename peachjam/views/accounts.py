from django.contrib.auth import get_user_model
from django.urls import reverse
from django.views.generic import UpdateView

from peachjam.forms import UserForm

User = get_user_model()


class EditAccountView(UpdateView):
    authentication_required = True
    model = User
    template_name = "user_account/edit.html"
    form_class = UserForm

    def get_success_url(self):
        return reverse("edit_account")

    def get_object(self, queryset=None):
        return self.request.user
