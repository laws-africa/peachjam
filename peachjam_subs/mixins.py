from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import render

from peachjam_subs.models import Product


class SubscriptionRequiredMixin(PermissionRequiredMixin):
    subscription_required_template = "peachjam_subs/subscription_required.html"

    def handle_no_permission(self):
        perm = (
            self.permission_required[0]
            if isinstance(self.permission_required, (list, tuple))
            else self.permission_required
        )

        lowest_product = Product.get_lowest_product_for_permission(perm)

        context = {
            "subscription_required": True,
            "lowest_product": lowest_product,
        }

        # Merge in extra context
        context.update(self.get_subscription_required_context())

        return render(
            self.request,
            self.get_subscription_required_template(),
            context,
            status=403,
        )

    def get_subscription_required_context(self):
        """
        Override this in your view to add extra context for the denied template.
        """
        return {}

    def get_subscription_required_template(self):
        return self.subscription_required_template
