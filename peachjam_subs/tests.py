from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from guardian.shortcuts import assign_perm

from peachjam_subs.models import (
    PricingPlan,
    Product,
    ProductOffering,
    Subscription,
    subscription_settings,
    validate_selectable_offering_catalog,
)


class SubscriptionTests(TestCase):
    fixtures = ["tests/countries", "tests/users", "tests/products"]

    def setUp(self):
        self.user = User.objects.first()

        self.product = Product.objects.get(pk=1)
        self.monthly_plan = PricingPlan.objects.create(
            name="Monthly Plan",
            price=Decimal("100.00"),
            period=PricingPlan.Period.MONTHLY,
        )
        self.annual_plan = PricingPlan.objects.create(
            name="Annual Plan",
            price=Decimal("100.00"),
            period=PricingPlan.Period.ANNUALLY,
        )
        self.product_offering = ProductOffering.objects.create(
            product=self.product, pricing_plan=self.monthly_plan
        )
        self.subscription = Subscription.objects.create(
            user=self.user,
            product_offering=self.product_offering,
            status=Subscription.Status.ACTIVE,
        )
        self.subscription.created_at = self.subscription.active_at = timezone.datetime(
            2023, 1, 1, tzinfo=timezone.utc
        )
        self.sub_settings = subscription_settings()
        for product in Product.objects.all():
            product.selectable_offerings.set(product.productoffering_set.all())

    @patch("django.utils.timezone.now")
    def test_start_of_current_period(self, mock_now):
        mock_now.return_value = timezone.datetime(2023, 8, 3, tzinfo=timezone.utc)
        self.assertEqual(date(2023, 8, 1), self.subscription.start_of_current_period())

        mock_now.return_value = timezone.datetime(2023, 8, 1, tzinfo=timezone.utc)
        self.assertEqual(date(2023, 8, 1), self.subscription.start_of_current_period())

        mock_now.return_value = timezone.datetime(2023, 8, 31, tzinfo=timezone.utc)
        self.assertEqual(date(2023, 8, 1), self.subscription.start_of_current_period())

    @patch("django.utils.timezone.now")
    def test_end_of_current_period(self, mock_now):
        mock_now.return_value = timezone.datetime(2023, 8, 3, tzinfo=timezone.utc)
        self.assertEqual(date(2023, 8, 31), self.subscription.end_of_current_period())

    @patch("django.utils.timezone.now")
    def test_prorate(self, mock_now):
        mock_now.return_value = timezone.datetime(2023, 8, 31, tzinfo=timezone.utc)
        days, value = self.subscription.prorate()
        self.assertEqual(1, days)
        # 1 day at (100/31 days) = 1 * 3.22 = 3.22
        self.assertAlmostEqual(Decimal("3.23"), value, places=2)

        mock_now.return_value = timezone.datetime(2023, 8, 30, tzinfo=timezone.utc)
        days, value = self.subscription.prorate()
        self.assertEqual(2, days)
        # 2 days at (100/31 days) = 2 * 3.22 = 6.44
        self.assertAlmostEqual(Decimal("6.45"), value, places=2)

        mock_now.return_value = timezone.datetime(2023, 8, 1, tzinfo=timezone.utc)
        days, value = self.subscription.prorate()
        self.assertEqual(31, days)
        # 31 days at (100/31 days) = 100
        self.assertAlmostEqual(Decimal("100.00"), value, places=2)

    def test_subscription(self):
        sub1 = Subscription.objects.create(
            user=self.user,
            product_offering=self.product_offering,
            status=Subscription.Status.PENDING,
        )
        sub1.activate()
        self.assertEqual(sub1.status, Subscription.Status.ACTIVE)
        self.assertIsNotNone(sub1.active_at)

    def test_pricing_plan_price_per_month(self):
        self.assertEqual("None100/month", self.monthly_plan.price_per_month)
        self.assertEqual("None8.33/month", self.annual_plan.price_per_month)

    def setup_trial(self):
        # clear out old subscription completely
        self.subscription.delete()
        # setup trials
        self.sub_settings.trial_product_offering = ProductOffering.objects.get(pk=3)
        self.sub_settings.save()

    def test_trial(self):
        self.setup_trial()

        # activate the subscription, which should start the trial
        sub = Subscription.objects.create(
            user=self.user,
            product_offering=self.product_offering,
            status=Subscription.Status.PENDING,
        )
        sub.activate()

        sub.refresh_from_db()
        # this subscription should not be active yet
        self.assertEqual(Subscription.Status.PENDING, sub.status)
        self.assertIsNotNone(sub.active_at)
        self.assertEqual(date.today() + timedelta(days=14), sub.starts_on)

        silver_offering = ProductOffering.objects.get(pk=3)
        trial = sub.trial_subscriptions.first()
        self.assertIsNotNone(trial)
        self.assertTrue(trial.is_trial)
        self.assertEqual(Subscription.Status.ACTIVE, trial.status)
        self.assertEqual(date.today() + timedelta(days=13), trial.ends_on)
        self.assertEqual(silver_offering, trial.product_offering)

        # pretend the trial started a few days ago
        active_at = sub.active_at = sub.active_at - timedelta(days=3)
        # subscription re-activates today
        sub.starts_on = date.today()
        sub.save()
        trial.active_at = trial.active_at - timedelta(days=3)
        # trial ended yesterday
        trial.ends_on = date.today() - timedelta(days=1)
        trial.save()

        # the trial ends because the real subscription activates
        sub.activate()
        sub.refresh_from_db()
        trial.refresh_from_db()

        self.assertEqual(Subscription.Status.ACTIVE, sub.status)
        # the activation date shouldn't change
        self.assertEqual(active_at, sub.active_at)

        self.assertEqual(Subscription.Status.CLOSED, trial.status)

    def test_upgrade_during_trial(self):
        """The user upgrades their plan during a trial period, which should cancel the trial and immediately upgrade
        them."""
        self.setup_trial()

        sub = Subscription.objects.create(
            user=self.user,
            product_offering=self.product_offering,
            status=Subscription.Status.PENDING,
        )
        # activate the subscription, which should start the trial
        sub.activate()

        sub.refresh_from_db()
        # this subscription should not be active yet
        self.assertEqual(Subscription.Status.PENDING, sub.status)

        trial = sub.trial_subscriptions.first()
        self.assertIsNotNone(trial)
        self.assertTrue(trial.is_trial)
        self.assertEqual(Subscription.Status.ACTIVE, trial.status)

        # silver should be an available offering
        silver_offering = ProductOffering.objects.get(pk=3)
        assign_perm("peachjam_subs.can_subscribe", self.user, silver_offering)
        self.assertIn(
            silver_offering.pk,
            [
                po.pk
                for po in ProductOffering.product_offerings_available_to_user(self.user)
            ],
        )

        # user upgrades to silver
        upgrade_sub = Subscription.objects.create(
            user=self.user,
            product_offering=silver_offering,
        )
        upgrade_sub.activate()

        upgrade_sub.refresh_from_db()
        sub.refresh_from_db()
        trial.refresh_from_db()

        self.assertEqual(Subscription.Status.ACTIVE, upgrade_sub.status)
        # both trial and old sub are closed
        self.assertEqual(Subscription.Status.CLOSED, sub.status)
        self.assertEqual(Subscription.Status.CLOSED, trial.status)

    def test_product_offerings_available_to_user_excludes_unconfigured_products(self):
        selectable_plan = PricingPlan.objects.create(
            name="Selectable Monthly Plan",
            price=Decimal("95.00"),
            period=PricingPlan.Period.MONTHLY,
        )
        selectable_offering = ProductOffering.objects.create(
            product=self.product,
            pricing_plan=selectable_plan,
        )

        non_selectable_plan = PricingPlan.objects.create(
            name="Hidden Staff Plan",
            price=Decimal("55.00"),
            period=PricingPlan.Period.MONTHLY,
        )
        non_selectable_product = Product.objects.create(
            name="No Selectable Product",
            tier=99,
        )
        non_selectable_offering = ProductOffering.objects.create(
            product=non_selectable_product,
            pricing_plan=non_selectable_plan,
        )

        assign_perm("peachjam_subs.can_subscribe", self.user, selectable_offering)
        assign_perm("peachjam_subs.can_subscribe", self.user, non_selectable_offering)

        offerings = list(ProductOffering.product_offerings_available_to_user(self.user))
        self.assertIn(selectable_offering, offerings)
        self.assertNotIn(non_selectable_offering, offerings)

    def test_validate_selectable_offering_catalog_rejects_non_monotonic_tier_price(
        self,
    ):
        bronze = Product.objects.create(name="Tier Bronze", tier=10)
        silver = Product.objects.create(name="Tier Silver", tier=20)
        bronze_monthly = ProductOffering.objects.create(
            product=bronze,
            pricing_plan=PricingPlan.objects.create(
                name="Tier Bronze Monthly",
                price=Decimal("20.00"),
                period=PricingPlan.Period.MONTHLY,
            ),
        )
        silver_monthly = ProductOffering.objects.create(
            product=silver,
            pricing_plan=PricingPlan.objects.create(
                name="Tier Silver Monthly",
                price=Decimal("10.00"),
                period=PricingPlan.Period.MONTHLY,
            ),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Selectable monthly pricing must increase with tier",
        ):
            validate_selectable_offering_catalog(
                [(bronze, [bronze_monthly]), (silver, [silver_monthly])]
            )

    def test_validate_selectable_offering_catalog_rejects_annual_below_monthly(self):
        bronze = Product.objects.create(name="Tier Bronze Two", tier=10)
        bronze_monthly = ProductOffering.objects.create(
            product=bronze,
            pricing_plan=PricingPlan.objects.create(
                name="Tier Bronze Two Monthly",
                price=Decimal("15.00"),
                period=PricingPlan.Period.MONTHLY,
            ),
        )
        bronze_annual = ProductOffering.objects.create(
            product=bronze,
            pricing_plan=PricingPlan.objects.create(
                name="Tier Bronze Two Annual",
                price=Decimal("12.00"),
                period=PricingPlan.Period.ANNUALLY,
            ),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "annual selectable price",
        ):
            validate_selectable_offering_catalog(
                [(bronze, [bronze_monthly, bronze_annual])]
            )

    def test_validate_selectable_offering_catalog_allows_mixed_period_products(self):
        monthly_only = Product.objects.create(name="Monthly Only", tier=10)
        annual_only = Product.objects.create(name="Annual Only", tier=20)
        monthly_offering = ProductOffering.objects.create(
            product=monthly_only,
            pricing_plan=PricingPlan.objects.create(
                name="Monthly Only Plan",
                price=Decimal("50.00"),
                period=PricingPlan.Period.MONTHLY,
            ),
        )
        annual_offering = ProductOffering.objects.create(
            product=annual_only,
            pricing_plan=PricingPlan.objects.create(
                name="Annual Only Plan",
                price=Decimal("40.00"),
                period=PricingPlan.Period.ANNUALLY,
            ),
        )

        # Should not raise: mixed monthly-only and annual-only products are allowed.
        validate_selectable_offering_catalog(
            [(monthly_only, [monthly_offering]), (annual_only, [annual_offering])]
        )

    def test_validate_selectable_offering_catalog_allows_free_monthly_and_annual(self):
        free_product = Product.objects.create(name="Free Product", tier=0)
        free_monthly = ProductOffering.objects.create(
            product=free_product,
            pricing_plan=PricingPlan.objects.create(
                name="Free Monthly Plan",
                price=Decimal("0.00"),
                period=PricingPlan.Period.MONTHLY,
            ),
        )
        free_annual = ProductOffering.objects.create(
            product=free_product,
            pricing_plan=PricingPlan.objects.create(
                name="Free Annual Plan",
                price=Decimal("0.00"),
                period=PricingPlan.Period.ANNUALLY,
            ),
        )

        validate_selectable_offering_catalog(
            [(free_product, [free_monthly, free_annual])]
        )
