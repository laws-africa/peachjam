from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import render
from django.utils.cache import add_never_cache_headers

from peachjam_subs.models import Product


class SubscriptionRequiredMixin(PermissionRequiredMixin):
    subscription_required_template = "peachjam_subs/_subscription_required.html"
    subscription_required_status = 200

    def handle_no_permission(self):
        context = self.build_subscription_required_context()
        response = self.render_subscription_required(context)
        add_never_cache_headers(response)
        return response

    def get_subscription_required_base_context(self):
        perm = (
            self.permission_required[0]
            if isinstance(self.permission_required, (list, tuple))
            else self.permission_required
        )

        lowest_product = Product.get_lowest_product_for_permission(perm)
        lowest_offering = self.get_lowest_offering_for_product(lowest_product)

        return {
            "subscription_required": True,
            "lowest_product": lowest_product,
            "lowest_offering": lowest_offering,
            "lowest_offering_is_free": bool(
                lowest_offering and lowest_offering.pricing_plan.price == 0
            ),
        }

    def get_subscription_required_context(self):
        """
        Override this in your view to add extra context for the denied template.
        """
        return {}

    def get_subscription_required_template(self):
        return self.subscription_required_template

    def build_subscription_required_context(self, **extra_context):
        context = self.get_subscription_required_base_context()
        context.update(self.get_subscription_required_context())
        if extra_context:
            context.update(extra_context)
        return context

    def get_lowest_offering_for_product(self, product):
        if not product:
            return None
        return product.get_best_available_offering_for_user(
            self.request.user if self.request.user.is_authenticated else None
        )

    def render_subscription_required(self, context):
        return render(
            self.request,
            self.get_subscription_required_template(),
            context,
            status=self.subscription_required_status,
        )
