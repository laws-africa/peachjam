import datetime

from countries_plus.models import Country
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse
from languages_plus.models import Language

from peachjam.models import (
    Court,
    Judgment,
    LeadingAuthority,
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

    def test_leading_authority_allows_any_legal_subject(self):
        authority = LeadingAuthority(
            judgment=self.make_judgment(),
            subject=LegalSubject.objects.create(
                name="Civil procedure",
                subject_type=LegalSubject.AREA_OF_LAW,
            ),
            editorial_note="A leading authority.",
            reviewed_on=datetime.date(2026, 8, 1),
        )

        authority.full_clean()


class LeadingAuthorityFragmentsTestCase(TestCase):
    fixtures = ["tests/courts", "tests/countries", "tests/languages"]

    def setUp(self):
        self.user = User.objects.create_user("subscriber@example.com")
        self.judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Foo v Bar",
        )
        self.authority = LeadingAuthority.objects.create(
            judgment=self.judgment,
            subject=LegalSubject.objects.create(
                name="Plascon-Evans rule",
                subject_type=LegalSubject.DOCTRINE,
            ),
            editorial_note="The leading formulation of the rule.",
            reviewed_on=datetime.date(2026, 8, 1),
            published=True,
        )
        LeadingAuthority.objects.create(
            judgment=self.judgment,
            subject=LegalSubject.objects.create(
                name="Motion proceedings",
                subject_type=LegalSubject.PROCEDURE,
            ),
            editorial_note="The procedural application of the rule.",
            reviewed_on=datetime.date(2026, 8, 2),
            published=True,
        )
        LeadingAuthority.objects.create(
            judgment=self.judgment,
            subject=LegalSubject.objects.create(
                name="Draft principle",
                subject_type=LegalSubject.PRINCIPLE,
            ),
            editorial_note="Not ready for publication.",
            reviewed_on=datetime.date(2026, 8, 3),
        )
        self.listing_url = reverse(
            "leading_authority_fragments", kwargs={"presentation": "listing"}
        )
        self.detail_url = reverse(
            "leading_authority_fragments", kwargs={"presentation": "detail"}
        )

    def grant_permission(self):
        self.user.user_permissions.add(
            Permission.objects.get(
                codename="view_leadingauthority",
                content_type__app_label="peachjam",
            )
        )
        self.client.force_login(self.user)

    def test_entitled_user_gets_listing_and_detail_fragments(self):
        self.grant_permission()

        listing_response = self.client.get(
            self.listing_url, {"doc_ids": str(self.judgment.pk)}
        )
        detail_response = self.client.get(
            self.detail_url, {"doc_ids": str(self.judgment.pk)}
        )

        self.assertContains(
            listing_response,
            f"outerHTML:.leading-authority-listing--{self.judgment.pk}",
        )
        self.assertNotContains(listing_response, "leading-authority-detail")
        self.assertContains(
            detail_response,
            f"outerHTML:.leading-authority-detail--{self.judgment.pk}",
        )
        self.assertNotContains(detail_response, "leading-authority-listing")
        for response in (listing_response, detail_response):
            self.assertContains(response, "Plascon-Evans rule")
            self.assertContains(response, "Motion proceedings")
            self.assertNotContains(response, "Draft principle")
            self.assertNotContains(response, "Not ready for publication.")
            self.assertNotContains(response, "data-leading-authority-document-id")
            self.assertIn("private", response.headers["Cache-Control"])
        self.assertContains(detail_response, "The leading formulation of the rule.")

    def test_unentitled_user_gets_no_authority_data(self):
        self.client.force_login(self.user)

        listing_response = self.client.get(
            self.listing_url, {"doc_ids": str(self.judgment.pk)}
        )
        detail_response = self.client.get(
            self.detail_url, {"doc_ids": str(self.judgment.pk)}
        )

        self.assertContains(
            listing_response,
            f"outerHTML:.leading-authority-listing--{self.judgment.pk}",
        )
        self.assertContains(
            detail_response,
            f"outerHTML:.leading-authority-detail--{self.judgment.pk}",
        )
        for response in (listing_response, detail_response):
            self.assertNotContains(response, "Plascon-Evans rule")
            self.assertNotContains(response, "The leading formulation of the rule.")
            self.assertIn("no-store", response.headers["Cache-Control"])

    def test_restricted_judgment_is_not_exposed_without_object_permission(self):
        self.grant_permission()
        self.judgment.restricted = True
        self.judgment.save(update_fields=["restricted"])

        response = self.client.get(self.detail_url, {"doc_ids": str(self.judgment.pk)})

        self.assertNotContains(response, "Plascon-Evans rule")
        self.assertNotContains(response, "The leading formulation of the rule.")

    def test_ids_are_deduplicated_and_invalid_values_are_ignored(self):
        self.grant_permission()

        response = self.client.get(
            self.listing_url,
            {"doc_ids": (f"{self.judgment.pk},invalid,{self.judgment.pk},0")},
        )

        self.assertContains(
            response,
            f'class="leading-authority-listing--{self.judgment.pk}"',
            count=1,
        )
