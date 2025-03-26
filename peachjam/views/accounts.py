from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.utils.translation import activate
from django.views import View
from django.views.generic import FormView
from django.views.generic.base import TemplateView

from peachjam.auth import user_display
from peachjam.forms import UserProfileForm

User = get_user_model()


class AccountsHomeView(LoginRequiredMixin, TemplateView):
    template_name = "user_account/home.html"


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
        response = super().form_valid(form)
        language_code = user.userprofile.preferred_language.iso_639_1
        # Set the language for the current session
        activate(language_code)
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            language_code,
            max_age=settings.LANGUAGE_COOKIE_AGE,
            path=settings.LANGUAGE_COOKIE_PATH,
            domain=settings.LANGUAGE_COOKIE_DOMAIN,
            secure=settings.LANGUAGE_COOKIE_SECURE,
            httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
            samesite=settings.LANGUAGE_COOKIE_SAMESITE,
        )
        return response


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
