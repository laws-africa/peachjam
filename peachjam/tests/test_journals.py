import datetime

from countries_plus.models import Country
from django.test import TestCase
from django.urls import reverse
from languages_plus.models import Language

from peachjam.models import Journal, JournalArticle


class JournalModelAndViewTests(TestCase):
    fixtures = [
        "tests/countries",
        "tests/languages",
        "documents/sample_documents",
    ]

    def setUp(self):
        super().setUp()
        self.journal = Journal.objects.create(
            title="Regional Law Journal",
            slug="regional-law-journal",
        )
        self.article = JournalArticle.objects.create(
            title="Fresh journal article",
            journal=self.journal,
            publisher="Publisher",
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
            jurisdiction=Country.objects.first(),
        )

    def test_journal_absolute_url(self):
        self.assertEqual(
            reverse("journal_detail", args=[self.journal.slug]),
            self.journal.get_absolute_url(),
        )

    def test_journal_detail_view_includes_follow_button(self):
        response = self.client.get(self.journal.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.article.title)
        self.assertContains(
            response,
            reverse("user_following_button") + f"?journal={self.journal.pk}",
        )
