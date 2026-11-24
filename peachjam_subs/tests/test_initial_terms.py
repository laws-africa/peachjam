from datetime import date

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from peachjam_subs.models import PricingPlan, ProductOffering, Subscription


class InitialTermTest(SimpleTestCase):
    def subscription(self, start, first_renewal):
        offering = ProductOffering(
            pricing_plan=PricingPlan(period="annually", price=100)
        )
        return Subscription(
            product_offering=offering,
            billing_anchor_on=start,
            initial_period_ends_on=first_renewal,
        )

    def test_initial_period_and_subsequent_anniversaries(self):
        sub = self.subscription(date(2026, 11, 24), date(2028, 2, 24))
        self.assertEqual(
            (date(2026, 11, 24), date(2028, 2, 23)),
            sub.period_bounds_for_date(date(2027, 12, 1)),
        )
        self.assertEqual(
            (date(2028, 2, 24), date(2029, 2, 23)),
            sub.period_bounds_for_date(date(2028, 2, 24)),
        )
        self.assertEqual(
            (date(2029, 2, 24), date(2030, 2, 23)),
            sub.period_bounds_for_date(date(2029, 3, 1)),
        )

    def test_leap_day_renewal(self):
        sub = self.subscription(date(2026, 11, 29), date(2028, 2, 29))
        self.assertEqual(
            (date(2028, 2, 29), date(2029, 2, 27)),
            sub.period_bounds_for_date(date(2028, 3, 1)),
        )

    def test_unset_preserves_standard_period(self):
        sub = self.subscription(date(2026, 11, 24), None)
        self.assertEqual(
            (date(2027, 11, 24), date(2028, 11, 23)),
            sub.period_bounds_for_date(date(2027, 12, 1)),
        )

    def test_positive_months(self):
        field = ProductOffering._meta.get_field("initial_period_months")
        with self.assertRaises(ValidationError):
            field.clean(0, ProductOffering())
        self.assertEqual(15, field.clean(15, ProductOffering()))
        self.assertIsNone(field.clean(None, ProductOffering()))

    def test_offerings_allow_discounts_by_default(self):
        self.assertTrue(ProductOffering().allow_discounts)
        self.assertTrue(ProductOffering().available_to_organisations)
