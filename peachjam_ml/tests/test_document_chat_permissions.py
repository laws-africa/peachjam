from datetime import date

from django.contrib.auth.models import Permission, User
from django.test import TestCase, override_settings

from peachjam.models import Country, GenericDocument, Language
from peachjam_ml.models import ChatThread
from peachjam_subs.models import (
    Feature,
    Product,
    ProductOffering,
    Subscription,
    subscription_settings,
)


@override_settings(ROOT_URLCONF="peachjam_ml.tests.urls")
class TestStartDocumentChatPermissions(TestCase):
    fixtures = ["tests/users", "tests/countries", "tests/languages", "tests/products"]

    def setUp(self):
        self.user = User.objects.get(pk=1)

        self.documents = [
            GenericDocument.objects.create(
                jurisdiction=Country.objects.first(),
                title=f"Test {idx}",
                date=date.today(),
                language=Language.objects.first(),
                frbr_uri_doctype="doc",
                frbr_uri_number=f"test-{idx}",
                frbr_uri_date="2024",
            )
            for idx in range(1, 4)
        ]

        self.product = Product.objects.get(pk=1)
        self.upgrade_product = Product.objects.get(pk=3)
        self.product.document_chat_limit = 2
        self.product.save()
        self.upgrade_product.document_chat_limit = 999999
        self.upgrade_product.save()

        sub_settings = subscription_settings()
        sub_settings.key_products.set([self.product, self.upgrade_product])
        sub_settings.save()

        permission = Permission.objects.get(
            content_type__app_label="peachjam_ml",
            codename="add_chatthread",
        )
        feature = Feature.objects.create(name="Document chat")
        feature.permissions.add(permission)
        self.product.features.add(feature)
        self.upgrade_product.features.add(feature)
        self.product.reset_permissions()
        self.upgrade_product.reset_permissions()

        self.offering = ProductOffering.objects.get(pk=1)

    def chat_url(self, document):
        return f"/api/documents/{document.pk}/chat"

    def activate_subscription(self, user):
        subscription = Subscription.objects.create(
            user=user,
            product_offering=self.offering,
            status=Subscription.Status.ACTIVE,
        )
        subscription.save()
        return subscription

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(self.chat_url(self.documents[0]))
        self.assertEqual(403, response.status_code)

    def test_authenticated_user_without_permission_gets_403(self):
        self.client.force_login(self.user)
        response = self.client.get(self.chat_url(self.documents[0]))
        self.assertEqual(403, response.status_code)

    def test_authenticated_user_with_permission_can_start_chat(self):
        self.activate_subscription(self.user)
        self.client.force_login(self.user)
        response = self.client.post(self.chat_url(self.documents[0]))
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload.get("thread_id"))
        self.assertIn(self.upgrade_product.name, payload.get("usage_limit_html", ""))
        self.assertIn(
            f" {self.product.document_chat_limit} ", payload.get("usage_limit_html", "")
        )

    def test_authenticated_user_over_limit_gets_403(self):
        self.activate_subscription(self.user)
        self.client.force_login(self.user)

        for document in self.documents[:2]:
            ChatThread.objects.create(user=self.user, document=document)

        response = self.client.post(self.chat_url(self.documents[2]))
        self.assertEqual(403, response.status_code)
        payload = response.json()
        self.assertIn("message_html", payload)
        self.assertIn(self.upgrade_product.name, payload["message_html"])
        self.assertIn(str(self.product.document_chat_limit), payload["message_html"])
        self.assertIn(f" {self.product.document_chat_limit} ", payload["message_html"])

    def test_usage_limit_html_in_get_when_no_thread(self):
        self.activate_subscription(self.user)
        self.client.force_login(self.user)

        response = self.client.get(self.chat_url(self.documents[0]))
        self.assertEqual(404, response.status_code)
        payload = response.json()
        self.assertIn(self.upgrade_product.name, payload.get("usage_limit_html", ""))
        self.assertIn(
            f" {self.product.document_chat_limit} ", payload.get("usage_limit_html", "")
        )

    def test_usage_limit_html_absent_when_unlimited(self):
        self.product.document_chat_limit = 999999
        self.product.save()

        self.activate_subscription(self.user)
        self.client.force_login(self.user)

        response = self.client.get(self.chat_url(self.documents[0]))
        self.assertEqual(404, response.status_code)
        payload = response.json()
        self.assertIsNone(payload.get("usage_limit_html"))
