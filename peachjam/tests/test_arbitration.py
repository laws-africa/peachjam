from datetime import date

from countries_plus.models import Country
from django.test import TestCase
from django.urls import reverse
from languages_plus.models import Language

from peachjam.models import ArbitralInstitution, ArbitrationAward, ArbitrationSeat


class ArbitrationTests(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def setUp(self):
        self.language = Language.objects.get(pk="en")
        self.country = Country.objects.get(pk="ZW")

        self.institution = ArbitralInstitution.objects.create(
            name="London Court of International Arbitration",
            acronym="LCIA",
        )
        self.other_institution = ArbitralInstitution.objects.create(
            name="International Chamber of Commerce",
            acronym="ICC",
        )
        self.seat = ArbitrationSeat.objects.create(
            city="London",
            country=self.country,
        )

    def create_award(self, institution, case_number, title):
        return ArbitrationAward.objects.create(
            title=title,
            date=date(2024, 10, 1),
            language=self.language,
            jurisdiction=self.country,
            frbr_uri_doctype="judgment",
            published=True,
            case_number=case_number,
            institution=institution,
            seat=self.seat,
            case_type=ArbitrationAward.CaseType.COMMERCIAL,
            nature_of_proceedings=ArbitrationAward.ArbitrationNature.INTERNATIONAL,
            outcome=ArbitrationAward.Outcome.CLAIMANT,
        )

    def test_case_number_is_preserved(self):
        award = self.create_award(self.institution, "ARB/98/8", "LCIA Award")
        self.assertEqual("ARB/98/8", award.case_number)

    def test_institution_list_links_to_detail(self):
        response = self.client.get(reverse("arbitral_institution_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("arbitral_institution_detail", args=[self.institution.acronym]),
        )

    def test_institution_detail_lists_awards(self):
        award = self.create_award(self.institution, "ARB/98/8", "LCIA Award")
        self.create_award(self.other_institution, "ICC2024/01", "ICC Award")

        response = self.client.get(
            reverse("arbitral_institution_detail", args=[self.institution.acronym])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, award.title)
        self.assertNotContains(response, "ICC Award")

    def test_award_detail_shows_breadcrumbs(self):
        award = self.create_award(self.institution, "ARB/98/8", "LCIA Award")
        response = self.client.get(
            reverse("arbitration_award_detail", args=[award.work_frbr_uri[1:]])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Arbitration Awards")
