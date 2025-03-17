from django.contrib.auth.models import Group, Permission, User
from django.db import models
from django.utils.translation import gettext_lazy as _

from peachjam.models import SingletonModel


class Feature(models.Model):
    name = models.CharField(max_length=100, unique=True)
    permissions = models.ManyToManyField(Permission, blank=True)
    hidden = models.BooleanField(
        default=False, help_text=_("Is this feature hidden from users?")
    )

    def __str__(self):
        s = self.name
        if self.hidden:
            s += " (" + _("hidden") + ")"
        return s


class Product(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    group = models.OneToOneField(Group, on_delete=models.CASCADE, null=True, blank=True)
    features = models.ManyToManyField(Feature, blank=True)

    def save(self, *args, **kwargs):
        if not self.group:
            self.group, created = Group.objects.get_or_create(
                name=f"Product: {self.name}"
            )
        super().save(*args, **kwargs)

    def reset_permissions(self):
        """Ensure the group's permissions are correct."""
        self.group.permissions.clear()
        for feature in self.features.all():
            self.group.permissions.add(*feature.permissions.all())

    def __str__(self):
        return self.name


class PricingPlan(models.Model):
    PERIODS = [("monthly", "Monthly"), ("annually", "Annually")]

    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    period = models.CharField(max_length=50, choices=PERIODS)

    def __str__(self):
        return f"{self.name} - {self.period}"


class ProductOffering(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    pricing_plan = models.ForeignKey(PricingPlan, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("product", "pricing_plan")

    def __str__(self):
        return f"{self.product} - {self.pricing_plan}"


class Subscription(models.Model):
    user = models.ForeignKey(
        User, related_name="subscriptions", on_delete=models.CASCADE
    )
    product_offering = models.ForeignKey(ProductOffering, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def product(self):
        return self.product_offering.product

    def __str__(self):
        return f"Subscription<{self.user.username} - {self.product_offering}"


class SubscriptionSettings(SingletonModel):
    default_product_offering = models.ForeignKey(
        ProductOffering,
        related_name="+",
        null=True,
        on_delete=models.SET_NULL,
        verbose_name=_("default product offering"),
    )

    def __str__(self):
        return "Subscription Settings"


def subscription_settings():
    return SubscriptionSettings.load()
