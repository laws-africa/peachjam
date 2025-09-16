from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import FormView
from django.views.generic.base import TemplateView

from peachjam.forms import UserProfileForm
from peachjam.models import DocumentAccessGroup

User = get_user_model()


class AccountView(LoginRequiredMixin, TemplateView):
    template_name = "user_account/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["document_access_groups"] = DocumentAccessGroup.objects.filter(
            group__in=self.request.user.groups.all()
        )
        return context


class EditAccountView(LoginRequiredMixin, FormView):
    template_name = "user_account/edit.html"
    form_class = UserProfileForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("my_account")

    def form_valid(self, form):
        user = form.save()
        language_code = user.userprofile.preferred_language.iso_639_1
        setattr(self.request, "set_language", language_code)
        messages.success(self.request, _("Your details have been updated."))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["document_access_groups"] = (
            DocumentAccessGroup.objects.filter(
                group__in=self.request.user.groups.all()
            ),
        )
        return context


class LoggedOutView(TemplateView):
    """When the user has logged out, they see this page with a Continue button. This gives us
    a chance to clear client-side state and cookies."""

    template_name = "account/logged_out.html"
    extra_context = {"reset_analytics": True}


class NavbarMenuView(TemplateView):
    template_name = "peachjam/_user_menu.html"
