import datetime

from countries_plus.models import Country
from django.core.exceptions import ValidationError
from django.test import TestCase
from languages_plus.models import Language

from peachjam.models import (
    Court,
    Judgment,
    LeadingAuthority,
    LeadingAuthoritySource,
    LegalSubject,
)


class LeadingAuthorityTestCase(TestCase):
    fixtures = ["tests/courts", "tests/countries", "tests/languages"]

    def make_judgment(self):
        return Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Foo v Bar",
        )

    def test_legal_subject_generates_slug(self):
        subject = LegalSubject.objects.create(
            name="Plascon-Evans rule",
            subject_type=LegalSubject.DOCTRINE,
        )

        self.assertEqual("plascon-evans-rule", subject.slug)

    def test_leading_authority_requires_doctrine_or_principle(self):
        authority = LeadingAuthority(
            judgment=self.make_judgment(),
            subject=LegalSubject.objects.create(
                name="Civil procedure",
                subject_type=LegalSubject.AREA_OF_LAW,
            ),
            editorial_note="A leading authority.",
            as_at_date=datetime.date(2026, 8, 1),
        )

        with self.assertRaisesMessage(
            ValidationError,
            "A leading authority must relate to a doctrine or principle.",
        ):
            authority.full_clean()

    def test_published_leading_authorities_excludes_drafts(self):
        judgment = self.make_judgment()
        published = LeadingAuthority.objects.create(
            judgment=judgment,
            subject=LegalSubject.objects.create(
                name="Plascon-Evans rule",
                subject_type=LegalSubject.DOCTRINE,
            ),
            editorial_note="The leading formulation of the rule.",
            as_at_date=datetime.date(2026, 8, 1),
            published=True,
        )
        LeadingAuthoritySource.objects.create(
            leading_authority=published,
            citation="Example source",
            url="https://example.com/source",
        )
        LeadingAuthority.objects.create(
            judgment=judgment,
            subject=LegalSubject.objects.create(
                name="Draft principle",
                subject_type=LegalSubject.PRINCIPLE,
            ),
            editorial_note="Not ready for publication.",
            as_at_date=datetime.date(2026, 8, 1),
        )

        judgment = Judgment.objects.for_document_table().get(pk=judgment.pk)

        self.assertEqual([published], judgment.published_leading_authorities)
        published = judgment.published_leading_authorities[0]
        with self.assertNumQueries(0):
            self.assertEqual(
                ["Example source"],
                [source.citation for source in published.sources.all()],
            )
