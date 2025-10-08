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
                    "subscription_is_trial": sub.is_trial,
                    "subscription_ends_on": int(sub.ends_on.timestamp()) if sub.ends_on else None,
                    "subscription_pricing_plan": str(sub.product_offering.pricing_plan),
                    "subscription_trial_replaces": sub.trial_replaces.product_offering.product.name
                    if sub.trial_replaces
                    else None,
                }
            )
        else:
            details.update(
                {
                    "is_paid": False,
                    "subscription_product": None,
                    "subscription_is_trial": False,
                    "subscription_ends_on": None,
                    "subscription_pricing_plan": None,
                    "subscription_trial_replaces": None,
                }
            )

        return details

    def get_subscription_details(self, subscription):
        details = self.get_common_details()
        details.update(
            {
                "product": subscription.product_offering.product.name,
                "pricing_plan": str(subscription.product_offering.pricing_plan),
                "is_trial": subscription.is_trial,
                "ends_on": int(subscription.ends_on.timestamp()) if subscription.ends_on else None,
                "trial_replaces": subscription.trial_replaces.product_offering.product.name
                if subscription.trial_replaces
                else None,
            }
        )
        return details

    def track_subscription_activated(self, subscription):
        if self.enabled():
            self.update_user_details(subscription.user)
            analytics.track(
                subscription.user.userprofile.tracking_id_str,
                "Subscription activated",
                self.get_subscription_details(subscription),
            )

    def track_subscription_closed(self, subscription):
        if self.enabled():
            self.update_user_details(subscription.user)
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
