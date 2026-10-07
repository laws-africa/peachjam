import datetime

from countries_plus.models import Country
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from languages_plus.models import Language

from peachjam.models import Journal, JournalArticle, VolumeIssue
from peachjam.views.journals import _volume_sort_key


class VolumeIssueSortTests(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def setUp(self):
        super().setUp()
        self.journal = Journal.objects.create(
            title="Test Journal",
            slug="test-journal",
        )

    def make_volume(self, title):
        return VolumeIssue(title=title, journal=self.journal)

    def sorted_titles(self, titles):
        volumes = [self.make_volume(t) for t in titles]
        return [v.title for v in sorted(volumes, key=_volume_sort_key)]

    def test_sorts_by_year_descending(self):
        titles = [
            "Vol. 3 No. 1 - January 1994",
            "Vol. 3 No. 1 - January 1996",
            "Vol. 3 No. 1 - January 1995",
        ]
        self.assertEqual(
            self.sorted_titles(titles),
            [
                "Vol. 3 No. 1 - January 1996",
                "Vol. 3 No. 1 - January 1995",
                "Vol. 3 No. 1 - January 1994",
            ],
        )

    def test_sorts_by_month_descending_within_year(self):
        titles = [
            "Vol. 4 No. 1 - March 1995",
            "Vol. 4 No. 1 - January 1995",
            "Vol. 4 No. 1 - September 1995",
        ]
        self.assertEqual(
            self.sorted_titles(titles),
            [
                "Vol. 4 No. 1 - September 1995",
                "Vol. 4 No. 1 - March 1995",
                "Vol. 4 No. 1 - January 1995",
            ],
        )

    def test_sorts_by_volume_ascending_within_year_and_month(self):
        titles = [
            "Vol. 5 No. 1 - January 1995",
            "Vol. 3 No. 1 - January 1995",
            "Vol. 4 No. 1 - January 1995",
        ]
        self.assertEqual(
            self.sorted_titles(titles),
            [
                "Vol. 3 No. 1 - January 1995",
                "Vol. 4 No. 1 - January 1995",
                "Vol. 5 No. 1 - January 1995",
            ],
        )

    def test_sorts_by_issue_ascending_within_year_month_and_volume(self):
        titles = [
            "Vol. 4 No. 8 - March 1995",
            "Vol. 4 No. 3 - March 1995",
            "Vol. 4 No. 11 - March 1995",
        ]
        self.assertEqual(
            self.sorted_titles(titles),
            [
                "Vol. 4 No. 3 - March 1995",
                "Vol. 4 No. 8 - March 1995",
                "Vol. 4 No. 11 - March 1995",
            ],
        )

    def test_combined_sort(self):
        titles = [
            "Vol. 4 No. 8 - March 1995",
            "Vol. 8 No. 2 - September 1998",
            "Vol. 5 No. 2 - September 1995",
            "Vol. 8 No. 1 - August 1998",
            "Vol. 2 No. 1 - August 1992",
        ]
        self.assertEqual(
            self.sorted_titles(titles),
            [
                "Vol. 8 No. 2 - September 1998",
                "Vol. 8 No. 1 - August 1998",
                "Vol. 5 No. 2 - September 1995",
                "Vol. 4 No. 8 - March 1995",
                "Vol. 2 No. 1 - August 1992",
            ],
        )


class VolumeIssueValidationTests(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def setUp(self):
        super().setUp()
        self.journal = Journal.objects.create(
            title="Test Journal",
            slug="test-journal",
        )

    def assertValid(self, title):
        v = VolumeIssue(title=title, journal=self.journal)
        v.clean()  # should not raise

    def assertInvalid(self, title):
        v = VolumeIssue(title=title, journal=self.journal)
        with self.assertRaises(ValidationError):
            v.clean()

    def test_valid_title_with_month(self):
        self.assertValid("Vol. 3 No. 1 - January 1993")

    def test_valid_title_with_month_no_spaces(self):
        self.assertValid("Vol.3 No.1 - March 1993")

    def test_invalid_title_missing_month(self):
        self.assertInvalid("Vol. 3 No. 1 - 1993")

    def test_invalid_title_missing_year(self):
        self.assertInvalid("Vol. 3 No. 1 - January")

    def test_invalid_title_missing_issue(self):
        self.assertInvalid("Vol. 3 - January 1993")

    def test_invalid_title_freeform(self):
        self.assertInvalid("Some random title")


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
