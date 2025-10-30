from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.generic import FormView
from django.views.generic.base import TemplateView

from peachjam.forms import TermsAcceptanceForm, UserProfileForm
from peachjam.models import DocumentAccessGroup, UserProfile

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


class AcceptTermsView(LoginRequiredMixin, FormView):
    template_name = "user_account/accept_terms.html"
    form_class = TermsAcceptanceForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and self._user_has_accepted_terms():
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def _user_has_accepted_terms(self):
        profile = getattr(self.request.user, "userprofile", None)
        return bool(getattr(profile, "accepted_terms_at", None))

    def _clean_next_url(self, default=None, allow_default=True):
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return next_url
        if allow_default:
            return default if default is not None else reverse("home_page")
        return ""

    def get_next_url(self):
        return self._clean_next_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["terms_url"] = reverse("terms_of_use")
        context["next"] = self._clean_next_url(allow_default=False)
        context["logout_url"] = reverse("account_logout")
        return context

    def get_success_url(self):
        return self.get_next_url()

    def form_valid(self, form):
        profile = getattr(self.request.user, "userprofile", None)
        if profile is None:
            profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        profile.accepted_terms_at = timezone.now()
        profile.save()
        return super().form_valid(form)
