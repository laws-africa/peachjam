from allauth.account.forms import ReauthenticateForm
from allauth.account.mixins import NextRedirectMixin
from allauth.account.views import ConfirmLoginCodeView as AllauthConfirmLoginCodeView
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.generic import FormView, UpdateView
from django.views.generic.base import TemplateView

from peachjam.forms import PasswordSignupForm, TermsAcceptanceForm, UserProfileForm
from peachjam.models import DocumentAccessGroup, UserProfile
from peachjam.views.mixins import AtomicPostMixin

User = get_user_model()


class UserAuthView(AllauthConfirmLoginCodeView):
    template_name = "account/user_auth.html"

    def _get_email_and_user(self):
        email = self._process.state.get("email")
        user = User.objects.filter(email=email).first() if email else None
        return email, user

    def get_next_url(self):
        email, user = self._get_email_and_user()
        if email and (user is None or not user.first_name):
            return self.passthrough_next_url(reverse("complete_profile"))
        return super().get_next_url()

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")

        if action == "resend":
            return self._handle_resend(request)
        elif action == "password_login":
            return self._handle_password_login(request)
        elif action == "signup_password":
            return self._handle_signup_password(request)

        return super().post(request, *args, **kwargs)

    def _handle_resend(self, request):
        self._process.send()
        self._process.record_resend()
        self._process.persist()
        return HttpResponseRedirect(request.get_full_path())

    def _handle_password_login(self, request):
        email, user = self._get_email_and_user()
        if not email or not user or not user.has_usable_password():
            return HttpResponseRedirect(request.get_full_path())

        form = ReauthenticateForm(user=user, data=request.POST)
        if form.is_valid():
            return self._process.finish(self.get_next_url())
        form_class = self.get_form_class()
        verify_form = form_class(code=self._process.code)
        ctx = self.get_context_data(form=verify_form)
        ctx["password_form"] = form
        ctx["show_password_section"] = True
        return self.render_to_response(ctx)

    def _handle_signup_password(self, request):
        email, user = self._get_email_and_user()
        if user:
            return HttpResponseRedirect(request.get_full_path())

        form = PasswordSignupForm(request.POST)
        if form.is_valid():
            new_user, resp = form.try_save(request)
            if resp:
                return resp
            if new_user:
                return self._process.finish(self.get_next_url())
        return self._render_with_signup_errors(signup_form=form)

    def _render_with_signup_errors(self, signup_form):
        self._extra_signup_form = signup_form
        form_class = self.get_form_class()
        verify_form = form_class(code=self._process.code)
        ctx = self.get_context_data(form=verify_form)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        email, user = self._get_email_and_user()

        is_existing = user is not None
        has_password = user.has_usable_password() if user else False

        ctx["is_existing_user"] = is_existing
        ctx["has_usable_password"] = has_password

        if is_existing and has_password and "password_form" not in ctx:
            ctx["password_form"] = ReauthenticateForm(user=user)

        extra_su = getattr(self, "_extra_signup_form", None)
        if not is_existing:
            ctx["signup_form"] = extra_su or PasswordSignupForm(
                initial={"email": email}
            )

        return ctx


class CompleteProfileView(NextRedirectMixin, LoginRequiredMixin, UpdateView):
    template_name = "account/complete_profile.html"
    fields = ["first_name", "last_name"]

    def get_object(self):
        return self.request.user

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["first_name"].required = True
        return form

    def get_default_success_url(self):
        return reverse("home_page")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.first_name:
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)


class AccountView(LoginRequiredMixin, TemplateView):
    template_name = "user_account/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["document_access_groups"] = DocumentAccessGroup.objects.filter(
            group__in=self.request.user.groups.all()
        )
        return context


class EditAccountView(AtomicPostMixin, LoginRequiredMixin, FormView):
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


class AcceptTermsView(AtomicPostMixin, LoginRequiredMixin, FormView):
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
