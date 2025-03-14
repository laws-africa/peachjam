from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Subscription


@receiver(post_save, sender=Subscription)
def manage_subscription_group(sender, instance, created, **kwargs):
    # TODO: check
    if created or "active" in kwargs["update_fields"]:
        if instance.active:
            instance.product_offering.product.group.user_set.add(instance.user)
        else:
            instance.product_offering.product.group.user_set.remove(instance.user)


@receiver(post_delete, sender=Subscription)
def remove_user_from_group(sender, instance, **kwargs):
    """Remove subscribing user from the product group when the subscription is deleted."""
    instance.product_offering.product.group.user_set.remove(instance.user)
