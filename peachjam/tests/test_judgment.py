import datetime

from countries_plus.models import Country
from django.test import TestCase
from languages_plus.models import Language

from peachjam.models import Author, CaseNumber, Judgment


class JudgmentTestCase(TestCase):
    fixtures = ["tests/authors", "tests/countries", "tests/languages"]
    maxDiff = None

    def test_assign_mnc(self):
        j = Judgment(
            language=Language.objects.get(pk="en"),
            author=Author.objects.first(),
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

    def test_assign_title(self):
        j = Judgment(
            language=Language.objects.get(pk="en"),
            author=Author.objects.first(),
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
            author=Author.objects.first(),
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
            author=Author.objects.first(),
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
