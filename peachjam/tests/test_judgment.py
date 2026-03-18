import datetime
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from countries_plus.models import Country
from django.core.exceptions import ValidationError
from django.test import TestCase
from languages_plus.models import Language

from peachjam.analysis.summariser import JudgmentSummary
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
        self.assertEqual("[2019] EACJ 1", j.mnc)

        j.assign_frbr_uri()
        self.assertEqual("/akn/za/judgment/eacj/2019/1", j.work_frbr_uri)

        mnc = j.mnc
        # it should not change
        j.assign_mnc()
        self.assertEqual(mnc, j.mnc)

        # it should not change
        j.save()
        j.assign_mnc()
        self.assertEqual(mnc, j.mnc)

    def test_assign_mnc_sn_override(self):
        j = Judgment(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        j.save()
        j.refresh_from_db()
        self.assertEqual("[2019] EACJ 1", j.mnc)

        j.serial_number_override = 999
        j.save()
        j.refresh_from_db()
        self.assertEqual("[2019] EACJ 999", j.mnc)
        self.assertEqual(999, j.serial_number)

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
        self.assertEqual("[2019] EACJ 999", j.mnc)

        # clearing the override doesn't automatically force a re-assignment of the serial number
        j.serial_number_override = None
        j.save()
        j.refresh_from_db()
        self.assertEqual("[2019] EACJ 999", j.mnc)
        self.assertEqual(999, j.serial_number)

    def test_assign_mnc_re_save(self):
        j = Judgment(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        j.save()
        j.refresh_from_db()
        self.assertEqual(1, j.serial_number)
        self.assertEqual("[2019] EACJ 1", j.mnc)

        j2 = Judgment(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 2, 2),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        j2.save()
        j2.refresh_from_db()
        self.assertEqual(2, j2.serial_number)
        self.assertEqual("[2019] EACJ 2", j2.mnc)

        # now re-save j
        j.save()
        j.refresh_from_db()
        self.assertEqual(1, j.serial_number)
        self.assertEqual("[2019] EACJ 1", j.mnc)

        j2.save()
        j2.refresh_from_db()
        self.assertEqual(2, j2.serial_number)
        self.assertEqual("[2019] EACJ 2", j2.mnc)

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
        self.assertEqual(
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
        self.assertEqual("Foo v Bar [2019] EACJ 1 (1 January 2019)", j.title)

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
        self.assertEqual(
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
        self.assertEqual("Foo v Bar [2019] EACJ 1 (1 janvier 2019)", j.title)

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

    @patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "test-openai-key",
            "LANGFUSE_PUBLIC_KEY": "test-langfuse-public-key",
            "LANGFUSE_SECRET_KEY": "test-langfuse-secret-key",
        },
        clear=False,
    )
    @patch("peachjam.analysis.summariser.langfuse.get_prompt")
    @patch("peachjam.analysis.summariser.OpenAI")
    def test_generate_summary_updates_judgment_fields(
        self,
        openai_cls,
        get_prompt,
    ):
        fake_summary = JudgmentSummary(
            issues=["Whether the appeal should succeed"],
            held=["The appeal was dismissed"],
            order="Appeal dismissed with costs.",
            summary="The court found no basis to interfere with the lower court's decision.",
            flynote="Appeal dismissed after no misdirection was shown.",
            blurb="Appeal dismissed.",
        )
        fake_response = SimpleNamespace(output_parsed=fake_summary)

        fake_openai = MagicMock()
        fake_openai.responses.parse.return_value = fake_response
        openai_cls.return_value = fake_openai

        fake_prompt = MagicMock()
        fake_prompt.compile.return_value = "Summarise this judgment."
        fake_prompt.config = {"model": "gpt-5-mini"}
        get_prompt.return_value = fake_prompt

        judgment = Judgment(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Foo v Bar",
        )
        judgment.save()
        doc_content = judgment.get_or_create_document_content(True)
        doc_content.set_content_html("<p>This is the judgment text.</p>")
        doc_content.save()

        judgment.generate_summary()
        judgment.refresh_from_db()

        self.assertEqual(fake_summary.blurb, judgment.blurb)
        self.assertEqual(fake_summary.summary, judgment.case_summary)
        self.assertEqual(fake_summary.flynote, judgment.flynote)
        self.assertEqual(fake_summary.held, judgment.held)
        self.assertEqual(fake_summary.issues, judgment.issues)
        self.assertEqual(fake_summary.order, judgment.order)
        self.assertTrue(judgment.summary_ai_generated)
        get_prompt.assert_called_once_with(
            "summarise/judgment",
            cache_ttl_seconds=30,
        )
        fake_openai.responses.parse.assert_called_once()

    @patch("peachjam.models.judgment.generate_judgment_summary")
    def test_content_text_change_triggers_summary_generation(
        self, generate_summary_task
    ):
        judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Foo v Bar",
        )

        doc_content = judgment.get_or_create_document_content(True)
        doc_content.set_content_html("<p>This is the judgment text.</p>")
        doc_content.save()

        self.assertTrue(
            any(
                call.args == (judgment.pk,)
                for call in generate_summary_task.call_args_list
            )
        )

    @patch("peachjam.models.judgment.generate_judgment_summary")
    def test_content_text_change_does_not_trigger_summary_until_anonymised(
        self, generate_summary_task
    ):
        judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Foo v Bar",
        )
        initial_calls = len(generate_summary_task.call_args_list)

        judgment.track_changes()
        judgment.must_be_anonymised = True
        judgment.save()
        self.assertEqual(initial_calls, len(generate_summary_task.call_args_list))

        doc_content = judgment.get_or_create_document_content(True)
        doc_content.set_content_html("<p>This is the judgment text.</p>")
        doc_content.save()

        self.assertEqual(initial_calls, len(generate_summary_task.call_args_list))

        judgment.refresh_from_db()
        judgment.track_changes()
        judgment.anonymised = True
        judgment.save()

        self.assertTrue(
            any(
                call.args == (judgment.pk,)
                for call in generate_summary_task.call_args_list
            )
        )

    @patch("peachjam.models.judgment.generate_judgment_summary")
    def test_existing_human_summary_blocks_auto_generation(self, generate_summary_task):
        judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Foo v Bar",
            case_summary="Editor-written summary",
            summary_ai_generated=False,
        )
        initial_calls = len(generate_summary_task.call_args_list)

        doc_content = judgment.get_or_create_document_content(True)
        doc_content.set_content_html("<p>This is the judgment text.</p>")
        doc_content.save()

        self.assertEqual(initial_calls, len(generate_summary_task.call_args_list))

        judgment.anonymised = True
        judgment.save()

        self.assertEqual(initial_calls, len(generate_summary_task.call_args_list))
