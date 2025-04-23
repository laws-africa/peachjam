import unittest

from django.contrib.auth.models import User

from peachjam.emails import CustomerIOTemplateBackend
from peachjam.models import CoreDocument


class TestCustomerIOTemplateBackendSupplementContext(unittest.TestCase):
    fixtures = [
        "tests/countries",
        "tests/courts",
        "test/languages",
        "documents/sample_documents",
    ]

    def setUp(self):
        self.user = User.objects.first()
        self.backend = CustomerIOTemplateBackend()
        self.context = {
            "APP_NAME": "PeachJam",
            "site": {"domain": "example.com", "url": "https://example.com"},
        }

    def test_supplement_context_with_user_and_document(self):
        document = CoreDocument.objects.first()

        self.context["user"] = self.user
        self.context["document"] = document
        self.context["nested"] = [{"foo": [document]}]

        self.backend.supplement_context(self.context)

        self.assertEqual(
            self.context["user"],
            {
                "email": self.user.email,
                "tracking_id": self.user.userprofile.tracking_id_str,
            },
        )

        self.assertIn("document", self.context)
        self.assertEqual(
            self.context["document"],
            {
                "title": document.title,
                "url_path": document.get_absolute_url(),
                "url": "https://localhost:8000/akn/za/bill/senate/2024-01-01/test-for-senate/eng@2024-01-01",
            },
        )
        self.assertEqual(
            self.context["nested"],
            [
                {
                    "foo": [
                        {
                            "title": document.title,
                            "url_path": document.get_absolute_url(),
                            "url": "https://localhost:8000/akn/za/bill/senate/2024-01-01/test-for-senate/eng@2024-01-01",  # noqa
                        }
                    ]
                }
            ],
        )
