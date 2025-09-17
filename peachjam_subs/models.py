import logging
from datetime import timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import Group, Permission, User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_fsm import GET_STATE, FSMField, transition
from guardian.shortcuts import get_objects_for_user

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

The SubscriptionSettings singleton model holds global settings for subscriptions, such as the default product offering
for new users (should be free). The key products are the ones that should be shown on the pricing page. This allows
us to exclude certain products that are only available by special arrangement.

Per-object permissions are used to control access to product offerings. A user must have the "can_subscribe" permission
for a product offering to be able to subscribe to it. This is managed by django-guardian.

Trial subscriptions are supported. They are activated the first time a user subscribes to a paid product, if the
product is a higher tier than the user's current product. The trial subscription is linked to the paid subscription
it replaces. The paid subscription is configured to activate when the trial subscription ends. When the real
subscription truly activates, the trial is closed. If the user upgrades in the mean time, both the trial and the
replaced subscription are closed.

See workflow here: https://mermaid.live/edit#pako:eNqNUs1um0AQfpXRXEsse4HURmoujcQD4FOFVG3ZsbMq7JL9SZpafvfOQmwldiIVLuzo-93hgJ1VhBV6eoxkOrrXcu_k0Brgx9hA0NMugN1B01SwdVr24OMv3zk9Bm1Na2boKF3QnR6lCYwE6aF5g4JG90_krqHbOkFn2XeE2vbqA-X6SnkGztCmubm7SzllF_STDHQx7nrrCWx4IHeGqHd1_BvGtmaGI8Yk05AyZtBr8xuCZUQGZBRf0TN8gVVxwfskwDSmnzLAt8TMYGQNbfYZ-MA1_UmuPDW62sAUIzn7_yk9VUil59knmnHklSsCFR1nmS1eReqkzSKjfOFcFw71tcNMaM6z9GKGe6cVVsFFynAgN8h0xEPitMjrGKjFij8V7WTsQ4utOTKNd_7D2uHEdDbuH7Dayd7zKY6Ko7z-r-ep46sh991GE7ASy-VmUsHqgH_4XIiFyIu1KEVZFsVquc7wBavbfCHEKt_cliJfF_lGHDP8O_kuF-uv5fEfQkABYw
"""  # noqa

log = logging.getLogger(__name__)


class Feature(models.Model):
    name = models.CharField(max_length=100, unique=True)
    permissions = models.ManyToManyField(Permission, blank=True)
    ordering = models.IntegerField(default=0)

    class Meta:
        ordering = ("ordering",)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    group = models.OneToOneField(Group, on_delete=models.CASCADE, null=True, blank=True)
    features = models.ManyToManyField(Feature, blank=True)
    key_features = models.ManyToManyField(
        Feature,
        blank=True,
        help_text="These features are highlighted in the product listing.",
        related_name="+",
    )
    default_offering = models.ForeignKey(
        "peachjam_subs.ProductOffering",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    # used to compare products
    tier = models.IntegerField(default=10)

    saved_document_limit = models.IntegerField(
        default=999999,
        help_text="The is the maximum number of documents a user can save.",
    )
    folder_limit = models.IntegerField(
        default=999999,
        help_text="The is the maximum number of folders a user can create.",
    )

    FEATURES_WITH_LIMIT = [
        "saved_document_limit",
        "folder_limit",
    ]

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

    def key_features_sorted(self):
        return self.key_features.all().order_by("ordering")

    def __str__(self):
        return self.name

    @classmethod
    def get_lowest_product_for_permission(cls, perm):
        """
        Return the best (lowest tier) product offering that includes the given permission.
        Accepts either 'app_label.codename' or just 'codename'.
        """
        # If perm looks like "app_label.codename", split it
        if "." in perm:
            app_label, codename = perm.split(".", 1)
        else:
            # Lookup the Permission by codename only (could raise MultipleObjectsReturned if not unique)
            try:
                permission = Permission.objects.get(codename=perm)
            except Permission.DoesNotExist:
                return None
            app_label, codename = permission.content_type.app_label, permission.codename

        product = (
            subscription_settings()
            .key_products.filter(
                features__permissions__content_type__app_label=app_label,
                features__permissions__codename=codename,
            )
            .order_by("tier")
            .first()
        )
        return product

    @classmethod
    def get_user_upgrade_products(cls, user, feature=None, count=None):
        """
        Return a queryset of Product objects that are upgrades for the user.
        If feature and count are given, filter upgrades to those that raise the limit.
        """
        active_subscription = Subscription.objects.active_for_user(user).first()
        products = subscription_settings().key_products.all()

        if active_subscription:
            current_tier = active_subscription.product_offering.product.tier
            products = products.filter(tier__gt=current_tier)

        if feature and count is not None:
            if feature not in cls.FEATURES_WITH_LIMIT:
                raise ValueError(f"Unknown feature: {feature}")
            products = products.filter(**{f"{feature}__gt": count})

        return products.order_by("tier")


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

    def format_price_per_period(self, price=None):
        price = self.price if price is None else price
        if price:
            return f"{self.format_price(price)}/{self.period_singular}"
        return _("FREE")

    @property
    def price_per_period(self):
        return self.format_price_per_period()

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
        permissions = [
            ("can_subscribe", "Can subscribe to this offering"),
        ]

    def __str__(self):
        return f"{self.product} - {self.pricing_plan}"

    @classmethod
    def product_offerings_available_to_user(cls, user):
        """Return a queryset of ProductOffering objects available to the user."""
        return (
            get_objects_for_user(user, "peachjam_subs.can_subscribe", klass=cls)
            .exclude(
                # exclude currently active subscription
                pk__in=Subscription.objects.active_for_user(user).values_list(
                    "product_offering", flat=True
                )
            )
            .order_by("-pricing_plan__price")
        )


class SubscriptionManager(models.Manager):
    def active_for_user(self, user):
        """
        Returns the active subscription for a user, if it exists.
        """
        return self.filter(user=user, status=Subscription.Status.ACTIVE).order_by(
            "-active_at"
        )


class Subscription(models.Model):
    """A user's subscription to a product offering.

    Only one subscription can be active at a time for a user. There can be multiple pending subscriptions.

    Every day, just after midnight, the system activates subscriptions that have a start date of today. It then
    closes any active subscriptions that had an end date at or before yesterday. Because activating a new subscription
    also deactivates any existing subscription, this means that a user can be upgraded or downgraded to a different
    subscription tier by ensuring the new subscription starts the day after the old one ends.
    """

    class Status(models.TextChoices):
        """
        Flow diagrom:

        pending -> active -> closed
                -> closed
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

    is_trial = models.BooleanField(
        default=False, help_text="Whether this is a trial subscription"
    )
    """ If this is a trial subscription, then trial_replaces points to the subscription it is replacing. When this trial
    ends, the replaced subscription (if any) is re-activated. """
    trial_replaces = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="trial_subscriptions",
    )

    starts_on = models.DateField(
        null=True, blank=True, help_text="Date when the subscription becomes active"
    )
    ends_on = models.DateField(
        null=True, blank=True, help_text="Date when the subscription ends"
    )

    objects = SubscriptionManager()

    def can_activate(self):
        return self.starts_on is None or self.starts_on <= timezone.now().date()

    @property
    def product(self):
        return self.product_offering.product

    @property
    def is_active(self):
        return self.status == Subscription.Status.ACTIVE

    @property
    def is_pending(self):
        return self.status == Subscription.Status.PENDING

    @property
    def is_closed(self):
        return self.status == Subscription.Status.CLOSED

    @transition(
        field=status,
        source=[Status.PENDING],
        # can either go to active or remain pending, use the final status to determine
        target=GET_STATE(
            lambda self, *args, **kwargs: self.status, [Status.ACTIVE, Status.PENDING]
        ),
        conditions=[can_activate],
    )
    def activate(self):
        """Activate this subscription. This also closes any other active subscriptions for the user.

        If a trial upgrade is applicable to the user, then:

        - create a trial subscription and activate it, and link it back to this one
        - this subscription remains in pending, but `active_at` is set to now
        - the trial end date, and this subscription start date, are set appropriately
        """
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
            if sub.is_trial and sub.trial_replaces:
                log.info(
                    f"Subscription closes {sub} which is a trial, and so also closes {sub.trial_replaces}"
                )
                # the trial is being replaced by a new subscription, so close the replaced one too
                sub.trial_replaces.close()

        # it might already be set, if there was a trial subscription, and we don't want to lose that timestamp
        self.active_at = self.active_at or timezone.now()

        # set up a trial if applicable
        sub_settings = subscription_settings()
        trial_offering = sub_settings.get_trial_offering(self)
        if trial_offering:
            trial = Subscription.objects.create(
                user=self.user,
                product_offering=trial_offering,
                is_trial=True,
                trial_replaces=self,
                ends_on=timezone.now().date()
                + timedelta(days=sub_settings.trial_duration_days - 1),
            )

            # set this subscription to start when the trial ends
            self.starts_on = trial.ends_on + timedelta(days=1)

            log.info(f"Created trial subscription {trial} in place of {self}")
            trial.activate()
        else:
            self.status = Subscription.Status.ACTIVE

        self.save()

    @transition(
        field=status, source=[Status.ACTIVE, Status.PENDING], target=Status.CLOSED
    )
    def close(self):
        log.info(f"Closing subscription {self}")
        self.closed_at = timezone.now()
        self.status = Subscription.Status.CLOSED
        self.save()

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
        """This is always two days after the end of the current period, which is one day after the start of the next
        period. This avoids issues with billing on the same day as a subscription starts or ends."""
        return self.end_of_current_period() + timedelta(days=2)

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
        return subscription

    @classmethod
    def update_subscriptions(cls):
        """Activate pending subscriptions and close active subscriptions as needed."""
        today = timezone.now().date()

        # Activate pending subscriptions that should be active today
        for sub in cls.objects.filter(
            status=cls.Status.PENDING, starts_on__lte=today
        ).all():
            if sub.can_activate():
                sub.activate()

        # Close active subscriptions that have ended
        for sub in cls.objects.filter(
            status__in=[cls.Status.ACTIVE, cls.Status.PENDING], ends_on__lt=today
        ).all():
            sub.close()

        # ensure all users have a subscription
        for user in User.objects.filter(subscriptions__isnull=True).all():
            cls.get_or_create_active_for_user(user)

    def check_feature_limit(self, feature: str):
        """
        Check if this subscription's user has reached the limit for a feature.
        Returns:
            {
                "reached": bool,            # True if limit is reached
                "upgrade_product": Product or None,
            }
        """
        # get the configured limit for this feature
        limit = getattr(self.product_offering.product, feature, None)
        if limit is None:
            return {"reached": True, "upgrade_product": None}  # unknown feature = block

        # resolve the related manager
        feature_map = {
            "saved_document_limit": self.user.saved_documents,
            "folder_limit": self.user.folders,
        }
        manager = feature_map.get(feature)
        if not manager:
            return True, None

        count = manager.count()
        # within limit?
        if count < limit:
            return False, None

        # over limit → suggest upgrade
        upgrade = Product.get_user_upgrade_products(
            self.user,
            feature=feature,
            count=count,
        ).first()

        return True, upgrade


class SubscriptionSettings(SingletonModel):
    default_product_offering = models.ForeignKey(
        ProductOffering,
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Default product offering"),
    )
    key_products = models.ManyToManyField(
        Product,
        blank=True,
        help_text=_("These products are highlighted in the product listing."),
    )
    trial_product_offering = models.ForeignKey(
        ProductOffering,
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Trial product offering"),
        help_text=_("If set, this product offering is used for trials."),
    )
    trial_duration_days = models.IntegerField(
        default=14,
        verbose_name=_("Trial duration (days)"),
        help_text=_("Number of days for the trial period."),
    )

    class Meta:
        verbose_name = "Subscription Settings"
        verbose_name_plural = verbose_name

    def get_trial_offering(self, subscription):
        """Return the trial product offering if it is applicable to the given subscription.

        A trial is applicable if:
        - this is the first paid subscription for the user (i.e. no previous active or closed subscriptions)
        - this product has a lower tier than the trial product (i.e. it would be an upgrade)
        """
        if (
            self.trial_product_offering
            and not subscription.is_trial
            and self.trial_product_offering.product.tier
            > subscription.product_offering.product.tier
        ):
            # check if the user has had a previously activated, non-free subscription
            if (
                not Subscription.objects.filter(
                    user=subscription.user,
                    active_at__isnull=False,
                    product_offering__pricing_plan__price__gt=0,
                )
                .exclude(
                    pk=subscription.pk,
                    status=Subscription.Status.PENDING,
                )
                .exists()
            ):
                return self.trial_product_offering

    def __str__(self):
        return "Subscription Settings"


def subscription_settings():
    return SubscriptionSettings.load()
