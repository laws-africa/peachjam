import peachjam.customerio
from peachjam.customerio import analytics
from peachjam_subs.models import Subscription


class SubscriptionDetailsMixin:
    def get_user_details(self, user):
        details = super().get_user_details(user)

        # Add subscription details
        sub = Subscription.objects.active_for_user(user).first()
        if sub:
            details.update(
                {
                    "is_paid": sub.product_offering.pricing_plan.price > 0,
                    "subscription_product": sub.product_offering.product.name,
                }
            )
        else:
            details.update(
                {
                    "is_paid": False,
                    "subscription_product": None,
                }
            )

        return details

    def get_subscription_details(self, subscription):
        details = self.get_common_details()
        details.update(
            {
                "product": subscription.product_offering.product.name,
                "pricing_plan": str(subscription.product_offering.pricing_plan),
            }
        )
        return details

    def track_subscription_activated(self, subscription):
        if self.enabled():
            analytics.track(
                subscription.user.userprofile.tracking_id_str,
                "Subscription activated",
                self.get_subscription_details(subscription),
            )

    def track_subscription_closed(self, subscription):
        if self.enabled():
            analytics.track(
                subscription.user.userprofile.tracking_id_str,
                "Subscription closed",
                self.get_subscription_details(subscription),
            )


def with_mixin(base, mixin):
    return type(f"{mixin.__name__}{base.__name__}", (mixin, base), {})


peachjam.customerio.CustomerIO = with_mixin(
    peachjam.customerio.CustomerIO, SubscriptionDetailsMixin
)
