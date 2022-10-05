import datetime

from countries_plus.models import Country
from django.test import TestCase
from languages_plus.models import Language

from peachjam.models import CaseNumber, Court, Judgment


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
            "Foo v Bar (2 of 1980) [2019] EACJ 1 (01 January 2019)", j.title
        )

    def test_assign_title_no_case_numbers(self):
        j = Judgment(
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Foo v Bar",
        )
        j.assign_mnc()
        j.assign_title()
        self.assertEquals("Foo v Bar [2019] EACJ 1 (01 January 2019)", j.title)

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
            "Foo v Bar (FooBar 99) [2019] EACJ 1 (01 January 2019)", j.title
        )
