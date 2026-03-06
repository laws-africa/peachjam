from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic.base import TemplateView
from django.views.generic.edit import DeleteView

from peachjam.models import pj_settings
from peachjam.views import AtomicPostMixin
from peachjam_subs.models import Subscription


class CancelSubscriptionView(AtomicPostMixin, LoginRequiredMixin, DeleteView):
    """Cancel a pending subscription."""

    model = Subscription
    http_method_names = ["post"]
    success_url = "my_account"

    def get_queryset(self):
        return self.model.objects.filter(
            user=self.request.user, status=Subscription.Status.PENDING
        )

    def form_valid(self, form):
        self.object.close()
        messages.success(
            self.request,
            _("Your pending subscription change has been cancelled."),
        )
        return redirect(self.get_success_url())


class CheckSubscriptionView(LoginRequiredMixin, View):
    """Check that the user has a subscription. In the vanilla peachjam_subs case, if a user has an account they
    have a subscription. Just redirect to the next url (or the homepage).
    """

    def get(self, request, *args, **kwargs):
        next_url = request.GET.get("next") or "home_page"
        return redirect(next_url)


class SubscribeView(TemplateView):
    template_name = "peachjam_subs/subscribe.html"

    def get(self, request, *args, **kwargs):
        if not pj_settings().allow_signups:
            return redirect("home_page")
        return super().get(request, *args, **kwargs)
