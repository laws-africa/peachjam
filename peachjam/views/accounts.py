from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import FormView
from django.views.generic.base import TemplateView

from peachjam.auth import user_display
from peachjam.forms import UserProfileForm

User = get_user_model()


class EditAccountView(LoginRequiredMixin, FormView):
    template_name = "user_account/edit.html"
    form_class = UserProfileForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("edit_account")

    def form_valid(self, form):
        user = form.save()
        language_code = user.userprofile.preferred_language.iso_639_1
        setattr(self.request, "set_language", language_code)
        messages.success(self.request, _("Your profile has been updated."))
        return super().form_valid(form)


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


class LoggedOutView(TemplateView):
    """When the user has logged out, they see this page with a Continue button. This gives us
    a chance to clear client-side state and cookies."""

    template_name = "account/logged_out.html"
    extra_context = {"reset_analytics": True}
