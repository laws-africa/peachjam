from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic.base import TemplateView
from django.views.generic.edit import DeleteView

from peachjam_subs.models import Subscription


class CancelSubscriptionView(LoginRequiredMixin, DeleteView):
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


class SubscribeView(TemplateView):
    template_name = "peachjam_subs/subscribe.html"
