from django.contrib.auth.models import User
from django.test import TestCase

from peachjam.emails import CustomerIOTemplateBackend
from peachjam.models import CoreDocument


class TestCustomerIOTemplateBackendSupplementContext(TestCase):
    fixtures = [
        "tests/languages",
        "tests/countries",
        "tests/users",
        "tests/courts",
        "documents/sample_documents",
    ]

    def setUp(self):
        self.user = User.objects.get(pk=1)
        self.backend = CustomerIOTemplateBackend()
        self.context = {}

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
                "url": "https://example.com" + document.get_absolute_url(),
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
                            "url": "https://example.com" + document.get_absolute_url(),
                        }
                    ]
                }
            ],
        )
