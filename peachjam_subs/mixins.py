from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import render

from peachjam_subs.models import Product


class SubscriptionRequiredMixin(PermissionRequiredMixin):
    def handle_no_permission(self):
        lowest_product = Product.get_lowest_product_for_permission(
            self.permission_required
        )
        if lowest_product:
            context = {"subscription_required": True, "lowest_product": lowest_product}
            return render(self.request, self.template_name, context, status=403)
        return super().handle_no_permission()
