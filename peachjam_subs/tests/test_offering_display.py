from django.core.exceptions import ValidationError
from django.forms.models import model_to_dict
from django.test import TestCase

from peachjam_subs.admin import ProductAdminForm
from peachjam_subs.models import (
    PricingPlan,
    Product,
    ProductOffering,
    validate_selectable_offering_catalog,
)


class OfferingDisplayTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name="Pro", description="Professional research tools", tier=20
        )
        self.plan = PricingPlan.objects.create(
            name="Annual", price=5940, period="annually"
        )
        self.regular = ProductOffering.objects.create(
            product=self.product, pricing_plan=self.plan
        )

    def test_optional_overrides_fall_back_independently(self):
        self.assertEqual(self.regular.display_name, self.product.name)
        self.assertEqual(self.regular.display_description, self.product.description)
        self.regular.name_override = "Pro — Black Friday"
        self.assertEqual(self.regular.display_name, "Pro — Black Friday")
        self.assertEqual(self.regular.display_description, self.product.description)
        self.regular.description_override = "Get three extra months"
        self.assertEqual(self.regular.display_description, "Get three extra months")
        self.assertIn("Pro — Black Friday", str(self.regular))
        self.regular.name_override = ""
        self.assertEqual(self.regular.display_name, self.product.name)

    def test_promotion_can_share_product_and_plan_but_not_selectable_period(self):
        promotion = ProductOffering.objects.create(
            product=self.product,
            pricing_plan=self.plan,
            name_override="Black Friday",
            initial_period_months=15,
        )
        self.product.selectable_offerings.set([promotion])
        validate_selectable_offering_catalog([(self.product, [promotion])])
        self.assertNotEqual(self.regular.pk, promotion.pk)
        with self.assertRaisesMessage(
            ValidationError, "more than one selectable annually"
        ):
            validate_selectable_offering_catalog(
                [(self.product, [self.regular, promotion])]
            )

    def test_admin_uses_submitted_tier_to_fix_catalogue(self):
        other = Product.objects.create(name="Essentials", tier=30)
        offering = ProductOffering.objects.create(
            product=other,
            pricing_plan=PricingPlan.objects.create(
                name="Essentials annual", price=3132, period="annually"
            ),
        )
        self.product.selectable_offerings.set([self.regular])
        other.selectable_offerings.set([offering])
        data = model_to_dict(other)
        data["tier"] = 10
        form = ProductAdminForm(data=data, instance=other)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        other.refresh_from_db()
        self.assertEqual(other.tier, 10)

        data["tier"] = 30
        form = ProductAdminForm(data=data, instance=other)
        self.assertFalse(form.is_valid())
        self.assertIn("pricing must increase with tier", str(form.non_field_errors()))
        other.refresh_from_db()
        self.assertEqual(other.tier, 10)
