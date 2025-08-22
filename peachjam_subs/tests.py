from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from peachjam_subs.models import PricingPlan, Product, ProductOffering, Subscription


class SubscriptionTests(TestCase):
    fixtures = ["tests/countries", "tests/users", "tests/products"]

    def setUp(self):
        self.user = User.objects.first()

        self.product = Product.objects.first()
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
            created_at=timezone.now(),
        )
        self.subscription.created_at = timezone.datetime(
            2023, 1, 1, tzinfo=timezone.utc
        )

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
            created_at=timezone.now(),
        )
        sub1.activate()
        self.assertEqual(sub1.status, Subscription.Status.ACTIVE)
        self.assertIsNotNone(sub1.active_at)
        sub1.refresh_from_db()
        self.assertEqual(sub1.status, Subscription.Status.ACTIVE)
        self.assertIsNotNone(sub1.active_at)
