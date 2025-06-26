from unittest.mock import Mock

from django.contrib.auth.models import User
from django.test import TestCase

from peachjam.emails import CustomerIOTemplateBackend
from peachjam.models import CoreDocument
from peachjam_search.serializers import SearchHit


class TestCustomerIOTemplateBackendSupplementContext(TestCase):
    maxDiff = None

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
                "blurb": None,
                "flynote": None,
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
                            "flynote": None,
                            "blurb": None,
                        }
                    ]
                }
            ],
        )

    def test_search_hit(self):
        document = CoreDocument.objects.first()
        fake = SearchHit.FakeDocument(
            {
                "title": "title",
                "expression_frbr_uri": "/akn/za/act/2009/1/eng@2023-10-01",
                "blurb": "blurb",
                "flynote": "flynote",
            }
        )

        es_hit = Mock()
        es_hit.meta = {}

        hit1 = SearchHit(
            es_hit=es_hit,
            id=10,
            index="test",
            score=100,
            position=1,
            expression_frbr_uri=document.expression_frbr_uri,
            document=document,
        )

        hit2 = SearchHit(
            es_hit=es_hit,
            id=20,
            index="test",
            score=100,
            position=2,
            expression_frbr_uri=fake.expression_frbr_uri,
            document=fake,
        )

        self.context["user"] = self.user
        self.context["hits"] = [hit1, hit2]
        self.backend.supplement_context(self.context)

        self.assertEqual(
            self.context["user"],
            {
                "email": self.user.email,
                "tracking_id": self.user.userprofile.tracking_id_str,
            },
        )

        self.assertEqual(
            self.context["hits"],
            [
                {
                    "id": 10,
                    "index": "test",
                    "score": 100,
                    "position": 1,
                    "expression_frbr_uri": document.expression_frbr_uri,
                    "best_match": False,
                    "highlight": {},
                    "pages": [],
                    "provisions": [],
                    "document": {
                        "title": document.title,
                        "url_path": document.get_absolute_url(),
                        "url": "https://example.com" + document.get_absolute_url(),
                        "blurb": None,
                        "flynote": None,
                    },
                },
                {
                    "id": 20,
                    "index": "test",
                    "score": 100,
                    "position": 2,
                    "expression_frbr_uri": fake.expression_frbr_uri,
                    "best_match": False,
                    "highlight": {},
                    "pages": [],
                    "provisions": [],
                    "document": {
                        "title": "title",
                        "url_path": fake.get_absolute_url(),
                        "url": "https://example.com" + fake.get_absolute_url(),
                        "blurb": "blurb",
                        "flynote": "flynote",
                    },
                },
            ],
        )
