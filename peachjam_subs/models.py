import logging
from datetime import timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import Group, Permission, User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_fsm import FSMField, transition

from peachjam.models import SingletonModel

"""
The subscriptions work as follows:

1. A feature is a permission that is included in a product. A feature is usually associated with multiple Django
   permissions which enable access to the feature.
2. A product is a collection of features, such as "Team Plan".
3. A pricing plan is a way to charge for a product, such as X per month.
4. A product offering is a product with a pricing plan. The same product may be offered under different pricing plans
   to reflect discounts, etc.
5. A subscription is a user's access to a product offering.
"""

log = logging.getLogger(__name__)


class Feature(models.Model):
    name = models.CharField(max_length=100, unique=True)
    permissions = models.ManyToManyField(Permission, blank=True)
    ordering = models.IntegerField(default=0)
    hidden = models.BooleanField(
        default=False, help_text=_("Is this feature hidden from users?")
    )

    class Meta:
        ordering = ("ordering",)

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
    # used to compare products
    tier = models.IntegerField(default=10)

    class Meta:
        ordering = ("tier",)

    def save(self, *args, **kwargs):
        if not self.group:
            self.group, created = Group.objects.get_or_create(
                name=f"Product: {self.name}"
            )
        super().save(*args, **kwargs)

    def reset_permissions(self):
        """Ensure the group's permissions are correct."""
        if self.group:
            self.group.permissions.clear()
            for feature in self.features.all():
                self.group.permissions.add(*feature.permissions.all())

    def __str__(self):
        return self.name


class PricingPlan(models.Model):
    class Period(models.TextChoices):
        MONTHLY = "monthly", _("Monthly")
        ANNUALLY = "annually", _("Annually")

    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    period = models.CharField(max_length=50, choices=Period.choices)
    currency_symbol = models.CharField(max_length=10, blank=True, null=True)

    @property
    def period_singular(self):
        return {
            self.Period.MONTHLY: _("month"),
            self.Period.ANNUALLY: _("year"),
        }.get(self.period, "")

    @property
    def price_str(self):
        return self.format_price(self.price)

    def format_price(self, price=None):
        price = self.price if price is None else price
        if price % 1 == 0:
            # no decimals
            return f"{self.currency_symbol}{price:.0f}"
        else:
            # two decimals
            return f"{self.currency_symbol}{price:.2f}"

    @property
    def price_per_period(self):
        if self.price:
            return f"{self.price_str}/{self.period_singular}"
        return _("FREE")

    def relative_delta(self):
        return {
            PricingPlan.Period.MONTHLY: relativedelta(months=1),
            PricingPlan.Period.ANNUALLY: relativedelta(years=1),
        }[self.period]

    def __str__(self):
        return f"{self.name}: {self.price_per_period}"


class ProductOffering(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    pricing_plan = models.ForeignKey(PricingPlan, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("product", "pricing_plan")

    def __str__(self):
        return f"{self.product} - {self.pricing_plan}"


class SubscriptionManager(models.Manager):
    def active_for_user(self, user):
        """
        Returns the active subscription for a user, if it exists.
        """
        return self.filter(user=user, status=Subscription.Status.ACTIVE).order_by(
            "-active_at"
        )


class Subscription(models.Model):
    class Status(models.TextChoices):
        """
        Flow diagrom:

        pending -> active
        active  -> closed
        """

        PENDING = "pending", _("Pending")
        ACTIVE = "active", _("Active")
        CLOSED = "closed", _("Closed")

    user = models.ForeignKey(
        User, related_name="subscriptions", on_delete=models.CASCADE
    )
    product_offering = models.ForeignKey(ProductOffering, on_delete=models.PROTECT)
    status = FSMField(choices=Status.choices, max_length=20, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    active_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = SubscriptionManager()

    @property
    def product(self):
        return self.product_offering.product

    @property
    def is_active(self):
        return self.status == Subscription.Status.ACTIVE

    @transition(field=status, source=[Status.PENDING], target=Status.ACTIVE)
    def activate(self):
        """Activate this subscription. This also closes any other active subscriptions for the user."""
        log.info(f"Activating subscription {self}")
        # ensure all other subscriptions for the user are closed
        for sub in (
            Subscription.objects.filter(
                user=self.user, status=Subscription.Status.ACTIVE
            )
            .exclude(pk=self.pk)
            .all()
        ):
            sub.close()
            sub.save()
        self.active_at = timezone.now()

    @transition(field=status, source=[Status.ACTIVE], target=Status.CLOSED)
    def close(self):
        log.info(f"Closing subscription {self}")
        self.closed_at = timezone.now()

    def end_of_current_period(self):
        """Returns the last day of the current subscription period."""
        today = timezone.now().date()
        start_date = self.active_at.date()
        period = self.product_offering.pricing_plan.period

        # Step 1: Find how many whole periods have passed since start_date
        elapsed = relativedelta(today, start_date)
        n = {
            PricingPlan.Period.MONTHLY: elapsed.years * 12 + elapsed.months,
            PricingPlan.Period.ANNUALLY: elapsed.years,
        }[period]

        # Step 2: Compute the end of the current period
        delta = self.product_offering.pricing_plan.relative_delta()
        current_period_start = start_date + n * delta
        current_period_end = current_period_start + delta - timedelta(days=1)

        return current_period_end

    def start_of_current_period(self):
        """Returns the first day of the current subscription period."""
        return (
            self.end_of_current_period()
            - self.product_offering.pricing_plan.relative_delta()
            + timedelta(days=1)
        )

    def next_billing_date(self):
        return self.end_of_current_period() + timedelta(days=1)

    def prorate(self):
        """Pro-rate this subscription for the remainder of the period, returning a (days, value) tuple describing
        the days remaining on the current subscription and the total value for those days.
        """
        # rate per day
        end_date = self.end_of_current_period()
        total_days = Decimal((end_date - self.start_of_current_period()).days + 1)
        daily_rate = self.product_offering.pricing_plan.price / total_days

        # remaining days and their value
        today = timezone.now().date()
        remaining_days = (end_date - today).days + 1  # includes today
        value = daily_rate * remaining_days

        return remaining_days, value

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.product_offering.product.group:
            if self.status == Subscription.Status.ACTIVE:
                self.product_offering.product.group.user_set.add(self.user)
            else:
                self.product_offering.product.group.user_set.remove(self.user)

    def __str__(self):
        return f"Subscription<#{self.pk} ({self.status}) for {self.user.username} - {self.product_offering}>"

    @classmethod
    def get_or_create_active_for_user(cls, user):
        """
        Get the active subscription for a user, or create a new one if it doesn't exist.
        """
        subscription = cls.objects.active_for_user(user).first()
        if not subscription:
            # Create a default subscription with the default product offering
            sub_settings = subscription_settings()
            if sub_settings.default_product_offering:
                subscription = cls.objects.create(
                    user=user,
                    product_offering=sub_settings.default_product_offering,
                )
                subscription.activate()
                subscription.save()
        return subscription


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
