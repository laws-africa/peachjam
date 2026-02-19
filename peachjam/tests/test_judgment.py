import datetime

from countries_plus.models import Country
from django.core.exceptions import ValidationError
from django.test import TestCase
from languages_plus.models import Language

from peachjam.models import CaseNumber, Court, CourtClass, Judgment, Locality


class JudgmentTestCase(TestCase):
    fixtures = ["tests/courts", "tests/countries", "tests/languages"]
    maxDiff = None

    def test_assign_mnc(self):
        j = Judgment(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        j.assign_mnc()
        self.assertEquals("[2019] EACJ 1", j.mnc)

        j.assign_frbr_uri()
        self.assertEquals("/akn/za/judgment/eacj/2019/1", j.work_frbr_uri)

        mnc = j.mnc
        # it should not change
        j.assign_mnc()
        self.assertEquals(mnc, j.mnc)

        # it should not change
        j.save()
        j.assign_mnc()
        self.assertEquals(mnc, j.mnc)

    def test_assign_mnc_sn_override(self):
        j = Judgment(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        j.save()
        j.refresh_from_db()
        self.assertEquals("[2019] EACJ 1", j.mnc)

        j.serial_number_override = 999
        j.save()
        j.refresh_from_db()
        self.assertEquals("[2019] EACJ 999", j.mnc)
        self.assertEquals(999, j.serial_number)

    def test_clear_serial_number_override(self):
        j = Judgment(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        j.serial_number_override = 999
        j.save()
        j.refresh_from_db()
        self.assertEquals("[2019] EACJ 999", j.mnc)

        # clearing the override doesn't automatically force a re-assignment of the serial number
        j.serial_number_override = None
        j.save()
        j.refresh_from_db()
        self.assertEquals("[2019] EACJ 999", j.mnc)
        self.assertEquals(999, j.serial_number)

    def test_assign_mnc_re_save(self):
        j = Judgment(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        j.save()
        j.refresh_from_db()
        self.assertEquals(1, j.serial_number)
        self.assertEquals("[2019] EACJ 1", j.mnc)

        j2 = Judgment(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 2, 2),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        j2.save()
        j2.refresh_from_db()
        self.assertEquals(2, j2.serial_number)
        self.assertEquals("[2019] EACJ 2", j2.mnc)

        # now re-save j
        j.save()
        j.refresh_from_db()
        self.assertEquals(1, j.serial_number)
        self.assertEquals("[2019] EACJ 1", j.mnc)

        j2.save()
        j2.refresh_from_db()
        self.assertEquals(2, j2.serial_number)
        self.assertEquals("[2019] EACJ 2", j2.mnc)

    def test_assign_title(self):
        j = Judgment(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Foo v Bar",
        )
        j.save()
        j.case_numbers.add(CaseNumber(number=2, year=1980), bulk=False)
        j.assign_mnc()
        j.assign_title()
        self.assertEquals(
            "Foo v Bar (2 of 1980) [2019] EACJ 1 (1 January 2019)", j.title
        )

    def test_assign_title_no_case_numbers(self):
        j = Judgment(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Foo v Bar",
        )
        j.assign_mnc()
        j.assign_title()
        self.assertEquals("Foo v Bar [2019] EACJ 1 (1 January 2019)", j.title)

    def test_assign_title_string_override(self):
        j = Judgment(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Foo v Bar",
        )
        j.save()
        j.case_numbers.add(
            CaseNumber(number=2, year=1980, string_override="FooBar 99"), bulk=False
        )
        j.assign_mnc()
        j.assign_title()
        self.assertEquals(
            "Foo v Bar (FooBar 99) [2019] EACJ 1 (1 January 2019)", j.title
        )

    def test_title_i18n(self):
        j = Judgment(
            language=Language.objects.get(pk="fr"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Foo v Bar",
        )
        j.assign_mnc()
        j.assign_title()
        self.assertEquals("Foo v Bar [2019] EACJ 1 (1 janvier 2019)", j.title)

    def test_court_rejects_locality_from_different_jurisdiction(self):
        za = Country.objects.get(pk="ZA")
        zm = Country.objects.get(pk="ZM")
        court_class = CourtClass.objects.first()
        locality = Locality.objects.create(
            name="Cape Town", code="cpt", jurisdiction=za
        )
        court = Court(
            name="Mismatched Court",
            code="mismatched-court",
            court_class=court_class,
            country=zm,
            locality=locality,
        )

        with self.assertRaises(ValidationError) as cm:
            court.full_clean()

        self.assertIn("locality", cm.exception.message_dict)

    def test_court_accepts_locality_from_same_jurisdiction(self):
        za = Country.objects.get(pk="ZA")
        court_class = CourtClass.objects.first()
        locality = Locality.objects.create(
            name="Johannesburg", code="jhb", jurisdiction=za
        )
        court = Court(
            name="Matching Court",
            code="matching-court",
            court_class=court_class,
            country=za,
            locality=locality,
        )

        court.full_clean()

    def test_judgment_save_clears_locality_when_court_has_none(self):
        za = Country.objects.get(pk="ZA")
        old_locality = Locality.objects.create(
            name="Durban", code="dbn", jurisdiction=za
        )
        court_without_locality = Court.objects.create(
            name="Court Without Locality",
            code="court-without-locality",
            country=za,
            locality=None,
        )

        judgment = Judgment(
            language=Language.objects.get(pk="en"),
            court=court_without_locality,
            date=datetime.date(2019, 1, 1),
            jurisdiction=za,
            locality=old_locality,
        )
        judgment.save()
        judgment.refresh_from_db()

        self.assertEqual(za, judgment.jurisdiction)
        self.assertIsNone(judgment.locality)
