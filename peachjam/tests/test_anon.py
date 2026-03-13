from datetime import timedelta

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.utils import timezone

from peachjam.models import Country, Judgment, Language
from peachjam.views.anon import DocumentAnonymiseSerializer


class DocumentAnonymiseSerializerTestCase(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.user = User.objects.create_user(
            username="anon-tester@example.com",
            email="anon-tester@example.com",
            password="password",
        )
        self.request = RequestFactory().put("/")
        self.request.user = self.user
        self.judgment = Judgment.objects.create(
            case_name="Original case",
            court_id=1,
            date=timezone.now().date(),
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        doc_content = self.judgment.get_or_create_document_content()
        doc_content.set_content_html("<h1>Original heading</h1><p>Original text</p>")
        doc_content.save()

    def test_update_persists_content_html_to_document_content(self):
        start = timezone.now()
        serializer = DocumentAnonymiseSerializer(
            instance=self.judgment,
            data={
                "case_name": "Anonymised case",
                "content_html": "<h1>Edited heading</h1><p>Edited body</p>",
                "published": True,
                "replacements": [],
                "activity_start": start.isoformat(),
                "activity_end": (start + timedelta(minutes=5)).isoformat(),
            },
            context={"request": self.request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.judgment.refresh_from_db()
        doc_content = self.judgment.document_content
        self.assertEqual("Anonymised case", self.judgment.case_name)
        self.assertTrue(self.judgment.anonymised)
        self.assertIn("Edited body", doc_content.source_html)
        self.assertIn("Edited body", doc_content.content_html)
        self.assertIn("Edited heading", doc_content.content_text)
        self.assertTrue(doc_content.toc_json)
