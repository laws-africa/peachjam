import datetime
from unittest.mock import MagicMock, patch

from countries_plus.models import Country
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.template.loader import render_to_string
from django.test import TestCase
from languages_plus.models import Language

from peachjam.analysis.summariser import JudgmentSummary
from peachjam.models import (
    CaseNumber,
    Court,
    CourtClass,
    CourtRegistry,
    Judgment,
    Locality,
)


class JudgmentTestCase(TestCase):
    fixtures = ["tests/courts", "tests/countries", "tests/languages"]
    maxDiff = None

    def make_judgment(self):
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
        return judgment

    def make_summary(
        self,
        flynote,
        summary="The court found no basis to interfere with the lower court's decision.",
    ):
        return JudgmentSummary(
            issues=["Whether the appeal should succeed"],
            held=["The appeal was dismissed"],
            order="Appeal dismissed with costs.",
            summary=summary,
            flynote=flynote,
            blurb="Appeal dismissed.",
        )

    def test_flynote_lines_splits_and_trims_multiline_flynotes(self):
        judgment = Judgment(flynote=" Line one \n\nLine two\n  Line three  ")
        self.assertEqual(["Line one", "Line two", "Line three"], judgment.flynote_lines)

    def test_grouped_flynote_lines_groups_maximal_common_ancestors(self):
        judgment = Judgment(
            flynote=(
                "Customs law — Customs and excise act — Diesel refund scheme — "
                "Interpretation of Note 6(f)(ii)(cc) — "
                "joint venture as substantive authorised user\n"
                "Customs law — Customs and excise act — Diesel refund scheme — "
                "Interpretation of Note 6(f)(ii)(cc) — "
                "Note 5 discretion to pay refunds to third parties on good cause shown\n"
                "Customs law — internal appeal jurisdiction — "
                "administrative-law duty to consider discretionary relief\n"
                "Customs law — internal appeal jurisdiction — "
                "NAC cannot introduce new grounds or increase original quantum"
            )
        )

        self.assertEqual(
            [
                {
                    "text": (
                        "Customs law — Customs and excise act — Diesel refund scheme — "
                        "Interpretation of Note 6(f)(ii)(cc)"
                    ),
                    "children": [
                        {
                            "text": "joint venture as substantive authorised user",
                            "children": [],
                        },
                        {
                            "text": "Note 5 discretion to pay refunds to third parties on good cause shown",
                            "children": [],
                        },
                    ],
                },
                {
                    "text": "Customs law — internal appeal jurisdiction",
                    "children": [
                        {
                            "text": "administrative-law duty to consider discretionary relief",
                            "children": [],
                        },
                        {
                            "text": "NAC cannot introduce new grounds or increase original quantum",
                            "children": [],
                        },
                    ],
                },
            ],
            judgment.grouped_flynote_lines,
        )

    def test_grouped_flynote_lines_keeps_original_order(self):
        judgment = Judgment(
            flynote=(
                "Zebra law — first point\n"
                "Alpha law — second point\n"
                "Beta law — third point"
            )
        )

        self.assertEqual(
            [
                {"text": "Zebra law — first point", "children": []},
                {"text": "Alpha law — second point", "children": []},
                {"text": "Beta law — third point", "children": []},
            ],
            judgment.grouped_flynote_lines,
        )

    def test_grouped_flynote_lines_groups_en_dash_paths(self):
        judgment = Judgment(
            flynote=(
                "Civil procedure – Intervention (Rule 12) – requires direct and substantial interest; "
                "non-joinder fatal\n"
                "Civil procedure – Rule 45A – cannot be used to suspend non-executable orders or mount "
                "collateral challenges; locus standi required\n"
                "Insolvency law – Sequestration – Final order under s 12(1)(a)–(c) – statutory requirements "
                "established (liquidated debt, insolvency, advantage to creditors) – court’s discretion "
                "exercised where no special circumstances shown"
            )
        )

        self.assertEqual(
            [
                {
                    "text": "Civil procedure",
                    "children": [
                        {
                            "text": (
                                "Intervention (Rule 12) — requires direct and substantial interest; "
                                "non-joinder fatal"
                            ),
                            "children": [],
                        },
                        {
                            "text": (
                                "Rule 45A — cannot be used to suspend non-executable orders or mount "
                                "collateral challenges; locus standi required"
                            ),
                            "children": [],
                        },
                    ],
                },
                {
                    "text": (
                        "Insolvency law — Sequestration — Final order under s 12(1)(a)–(c) — statutory "
                        "requirements established (liquidated debt, insolvency, advantage to creditors) — "
                        "court’s discretion exercised where no special circumstances shown"
                    ),
                    "children": [],
                },
            ],
            judgment.grouped_flynote_lines,
        )

    def test_grouped_flynote_lines_groups_spaced_ascii_dash_paths(self):
        judgment = Judgment(
            flynote=(
                "Administrative Law - Judicial Review - Legality Review - Unlawful Appointment - "
                "Jurisdiction, Delay, Legality of Municipal Appointments\n"
                "Administrative Law - Judicial Review - Legality Review - Unlawful Appointment - "
                "Delay and prejudice"
            )
        )

        self.assertEqual(
            [
                {
                    "text": (
                        "Administrative Law — Judicial Review — Legality Review — "
                        "Unlawful Appointment"
                    ),
                    "children": [
                        {
                            "text": "Jurisdiction, Delay, Legality of Municipal Appointments",
                            "children": [],
                        },
                        {
                            "text": "Delay and prejudice",
                            "children": [],
                        },
                    ],
                }
            ],
            judgment.grouped_flynote_lines,
        )

    def test_grouped_flynote_lines_groups_ancestor_with_descendants(self):
        judgment = Judgment(
            flynote=(
                "Customs law — internal appeal jurisdiction\n"
                "Customs law — internal appeal jurisdiction — "
                "administrative-law duty to consider discretionary relief\n"
                "Customs law — internal appeal jurisdiction — "
                "NAC cannot introduce new grounds or increase original quantum"
            )
        )

        self.assertEqual(
            [
                {
                    "text": "Customs law — internal appeal jurisdiction",
                    "children": [
                        {
                            "text": "administrative-law duty to consider discretionary relief",
                            "children": [],
                        },
                        {
                            "text": "NAC cannot introduce new grounds or increase original quantum",
                            "children": [],
                        },
                    ],
                }
            ],
            judgment.grouped_flynote_lines,
        )

    def test_blurb_and_flynotes_renders_nested_groups(self):
        judgment = Judgment(
            blurb="Appeal dismissed.",
            flynote=(
                "Contract law — offer and acceptance\n" "Contract law — consideration"
            ),
        )

        html = render_to_string(
            "peachjam/judgment/_blurb_and_flynotes.html",
            {"document": judgment, "show_flynote_heading": True},
        )
        normalized_html = " ".join(html.split())

        self.assertIn("<h6", html)
        self.assertIn("Contract law", html)
        self.assertEqual(1, html.count("Contract law"))
        self.assertIn("— offer and acceptance", normalized_html)
        self.assertIn("— consideration", normalized_html)
        self.assertGreaterEqual(html.count("<ul"), 2)

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

    def test_judgment_cannot_save_without_court(self):
        judgment = Judgment(
            auto_assign_details=False,
            language=Language.objects.get(pk="en"),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Foo v Bar",
            title="Foo v Bar [2019] TEST 1 (1 January 2019)",
            citation="Foo v Bar [2019] TEST 1 (1 January 2019)",
            serial_number=1,
            mnc="[2019] TEST 1",
            frbr_uri_doctype="judgment",
            frbr_uri_actor="testcourt",
            frbr_uri_date="2019",
            frbr_uri_number="1",
        )

        with self.assertRaises(IntegrityError):
            judgment.save()

    def test_judgment_registry_sets_court_on_save(self):
        court = Court.objects.first()
        registry = CourtRegistry.objects.create(
            court=court,
            name="Main registry",
            code="main-registry",
        )
        judgment = Judgment(
            language=Language.objects.get(pk="en"),
            registry=registry,
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Foo v Bar",
        )

        judgment.save()
        judgment.refresh_from_db()

        self.assertEqual(court, judgment.court)

    @patch("peachjam.models.judgment.JudgmentSummariser")
    def test_generate_summary_updates_judgment_fields(self, summariser_cls):
        expected_flynote = (
            "Contract - Contract of sale of goods - Whether and under what circumstances "
            "a mere purchase order may amount to an agreement to sell\n"
            "Contract - Contract of sale of goods - Delivery - Mode of delivery - "
            "Agreement is silent on mode of delivery - Delivery in one lot presumed"
        )
        fake_summary = JudgmentSummary(
            issues=["Whether the appeal should succeed"],
            held=["The appeal was dismissed"],
            order="Appeal dismissed with costs.",
            summary="The court found no basis to interfere with the lower court's decision.",
            flynote=expected_flynote,
            blurb="Appeal dismissed.",
        )
        summariser = MagicMock()
        summariser.enabled.return_value = True
        summariser.summarise_judgment.return_value = fake_summary
        summariser_cls.return_value = summariser

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

        judgment.track_changes()
        judgment.generate_summary()
        judgment.refresh_from_db()

        self.assertEqual(fake_summary.blurb, judgment.blurb)
        self.assertEqual(fake_summary.summary, judgment.case_summary)
        self.assertEqual(expected_flynote, judgment.flynote)
        self.assertEqual(expected_flynote, judgment.flynote_raw)
        self.assertEqual(fake_summary.held, judgment.held)
        self.assertEqual(fake_summary.issues, judgment.issues)
        self.assertEqual(fake_summary.order, judgment.order)
        self.assertTrue(judgment.summary_ai_generated)
        summariser.summarise_judgment.assert_called_once_with(judgment)

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

    def test_serialise_flynote_tree(self):
        from peachjam.analysis.flynotes import FlynoteUpdater

        judgment = self.make_judgment()
        judgment.flynote_raw = (
            "Criminal law \u2014 admissibility \u2014 trial within a trial\n"
            "Administrative law \u2014 judicial review"
        )
        judgment.save()
        FlynoteUpdater().update_for_judgment(judgment)

        judgment.serialise_flynote_tree()
        self.assertEqual(
            judgment.flynote,
            "Administrative law \u2014 judicial review\n"
            "Criminal law \u2014 admissibility \u2014 trial within a trial",
        )
        self.assertEqual(judgment.flynote, judgment.flynote_raw)
