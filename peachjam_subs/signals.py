from django.contrib.auth import get_user_model
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .models import Feature, Product, Subscription, subscription_settings


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


@receiver(m2m_changed, sender=Feature.permissions.through)
def feature_permissions_changed(sender, instance, action, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"]:
        for product in instance.product_set.all():
            product.reset_permissions()


@receiver(m2m_changed, sender=Product.features.through)
def product_features_changed(sender, instance, action, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"]:
        instance.reset_permissions()


@receiver(post_save, sender=Feature)
def feature_saved(sender, instance, **kwargs):
    for product in instance.product_set.all():
        product.reset_permissions()


# peachjam_subs/signals.py


User = get_user_model()


@receiver(post_save, sender=User)
def create_default_subscription(sender, instance, created, **kwargs):
    if created:
        default_product_offering = subscription_settings().default_product_offering
        if default_product_offering:
            Subscription.objects.create(
                user=instance, product_offering=default_product_offering
            )
