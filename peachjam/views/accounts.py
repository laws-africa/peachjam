from django.contrib.auth import get_user_model
from django.urls import reverse
from django.views.generic import UpdateView

from peachjam.forms import UserEditorForm

User = get_user_model()


class EditAccountView(UpdateView):
    authentication_required = True
    model = User
    template_name = "user_account/edit.html"
    form_class = UserEditorForm

    def get_success_url(self):
        return reverse("edit_account")

    def get_object(self, queryset=None):
        return self.request.user

    def get_initial(self):
        initial = super(EditAccountView, self).get_initial()
        initial["first_name"] = self.request.user.first_name
        initial["last_name"] = self.request.user.last_name
        return initial
