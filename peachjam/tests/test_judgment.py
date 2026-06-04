import datetime
from types import SimpleNamespace
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
from peachjam.templatetags.peachjam import group_flynote_lines, group_linked_flynotes


class JudgmentTestCase(TestCase):
    fixtures = ["tests/courts", "tests/countries", "tests/languages"]
    maxDiff = None

    def assertGroupedFlynotesEqual(self, expected, judgment):
        self.assertEqual(
            expected,
            group_flynote_lines(judgment.flynote_lines),
        )

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

        self.assertGroupedFlynotesEqual(
            [
                {
                    "text": "Customs law",
                    "children": [
                        {
                            "text": (
                                "Customs and excise act — Diesel refund scheme — "
                                "Interpretation of Note 6(f)(ii)(cc)"
                            ),
                            "parts": [
                                "Customs and excise act",
                                "Diesel refund scheme",
                                "Interpretation of Note 6(f)(ii)(cc)",
                            ],
                            "child_indent": 48,
                            "children": [
                                {
                                    "text": "joint venture as substantive authorised user",
                                    "children": [],
                                },
                                {
                                    "text": (
                                        "Note 5 discretion to pay refunds to third parties on good cause shown"
                                    ),
                                    "children": [],
                                },
                            ],
                        },
                        {
                            "text": "internal appeal jurisdiction",
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
                }
            ],
            judgment,
        )

    def test_grouped_flynote_lines_keeps_original_order(self):
        judgment = Judgment(
            flynote=(
                "Zebra law — first point\n"
                "Alpha law — second point\n"
                "Beta law — third point"
            )
        )

        self.assertGroupedFlynotesEqual(
            [
                {"text": "Zebra law — first point", "children": []},
                {"text": "Alpha law — second point", "children": []},
                {"text": "Beta law — third point", "children": []},
            ],
            judgment,
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

        self.assertGroupedFlynotesEqual(
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
            judgment,
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

        self.assertGroupedFlynotesEqual(
            [
                {
                    "text": (
                        "Administrative Law — Judicial Review — Legality Review — "
                        "Unlawful Appointment"
                    ),
                    "parts": [
                        "Administrative Law",
                        "Judicial Review",
                        "Legality Review",
                        "Unlawful Appointment",
                    ],
                    "child_indent": 57,
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
            judgment,
        )

    def test_grouped_flynote_lines_compresses_single_child_paths_recursively(self):
        judgment = Judgment(
            flynote=(
                "Criminal law — concurrency of sentences — condonation of late appeal\n"
                "Criminal law — concurrency of sentences — link between offences\n"
                "Criminal law — sentencing — Prescribed minimum sentences — "
                "substantial and compelling circumstances — appellate interference only where sentencing "
                "discretion misdirected, disproportionate or vitiated"
            )
        )

        self.assertGroupedFlynotesEqual(
            [
                {
                    "text": "Criminal law",
                    "children": [
                        {
                            "text": "concurrency of sentences",
                            "children": [
                                {
                                    "text": "condonation of late appeal",
                                    "children": [],
                                },
                                {
                                    "text": "link between offences",
                                    "children": [],
                                },
                            ],
                        },
                        {
                            "text": (
                                "sentencing — Prescribed minimum sentences — "
                                "substantial and compelling circumstances — appellate interference only where "
                                "sentencing discretion misdirected, disproportionate or vitiated"
                            ),
                            "children": [],
                        },
                    ],
                },
            ],
            judgment,
        )

    def test_grouped_flynote_lines_keeps_explicit_ancestor_topic(self):
        judgment = Judgment(
            flynote=("Administrative law\n" "Administrative law — PAJA")
        )

        self.assertGroupedFlynotesEqual(
            [
                {
                    "text": "Administrative law",
                    "children": [
                        {
                            "text": "PAJA",
                            "children": [],
                        },
                    ],
                },
            ],
            judgment,
        )

    def test_group_linked_flynotes_groups_single_line_semicolon_branches(self):
        def node(name):
            node_obj = SimpleNamespace(name=name)
            slug = name.lower().replace(" ", "-")
            node_obj.get_absolute_url = lambda: f"/judgments/topics/{slug}/"
            return node_obj

        linked = [
            {
                "nodes": [
                    node("Family law"),
                    node("Matrimonial property act"),
                    node(
                        "Doctrine of notice inapplicable to contingent accrual claims"
                    ),
                ]
            },
            {
                "nodes": [
                    node("Family law"),
                    node("Matrimonial property act"),
                    node(
                        "accrual claim contingent until dissolution, not a proprietary right of occupation"
                    ),
                ]
            },
            {
                "nodes": [
                    node("Family law"),
                    node("PIE Act"),
                    node(
                        "eviction may be just and equitable where spouse has no vested right"
                    ),
                ]
            },
            {
                "nodes": [
                    node("Family law"),
                    node("Procedure"),
                    node(
                        "proper form of order when jurisdictional threshold not met "
                        "(confirmation vs striking off roll)."
                    ),
                ]
            },
        ]

        grouped = group_linked_flynotes(linked)

        def simplify(groups):
            return [
                {
                    "nodes": [node.name for node in item["nodes"]],
                    "children": simplify(item["children"]),
                }
                for item in groups
            ]

        self.assertEqual(
            [
                {
                    "nodes": ["Family law"],
                    "children": [
                        {
                            "nodes": ["Matrimonial property act"],
                            "children": [
                                {
                                    "nodes": [
                                        "Doctrine of notice inapplicable to contingent accrual claims"
                                    ],
                                    "children": [],
                                },
                                {
                                    "nodes": [
                                        "accrual claim contingent until dissolution, not a proprietary "
                                        "right of occupation"
                                    ],
                                    "children": [],
                                },
                            ],
                        },
                        {
                            "nodes": [
                                "PIE Act",
                                "eviction may be just and equitable where spouse has no vested right",
                            ],
                            "children": [],
                        },
                        {
                            "nodes": [
                                "Procedure",
                                "proper form of order when jurisdictional threshold not met "
                                "(confirmation vs striking off roll).",
                            ],
                            "children": [],
                        },
                    ],
                },
            ],
            simplify(grouped),
        )

    def test_group_linked_flynotes_keeps_explicit_ancestor_topic(self):
        def node(name):
            node_obj = SimpleNamespace(name=name)
            slug = name.lower().replace(" ", "-")
            node_obj.get_absolute_url = lambda: f"/judgments/topics/{slug}/"
            return node_obj

        grouped = group_linked_flynotes(
            [
                {"nodes": [node("Administrative law")]},
                {"nodes": [node("Administrative law"), node("PAJA")]},
            ]
        )

        def simplify(groups):
            return [
                {
                    "nodes": [node.name for node in item["nodes"]],
                    "children": simplify(item["children"]),
                }
                for item in groups
            ]

        self.assertEqual(
            [
                {
                    "nodes": ["Administrative law"],
                    "children": [
                        {
                            "nodes": ["PAJA"],
                            "children": [],
                        }
                    ],
                },
            ],
            simplify(grouped),
        )

    def test_blurb_and_flynotes_renders_grouped_linked_flynotes_without_repeating_ancestors(
        self,
    ):
        def node(name):
            slug = name.lower().replace(" ", "-")
            node_obj = SimpleNamespace(name=name)
            node_obj.get_absolute_url = lambda: f"/judgments/topics/{slug}/"
            return node_obj

        document = SimpleNamespace(
            blurb="Appeal dismissed.",
            flynote="",
            flynote_lines=[],
            linked_flynotes=[
                {
                    "nodes": [
                        node("Family law"),
                        node("Matrimonial property act"),
                        node(
                            "Doctrine of notice inapplicable to contingent accrual claims"
                        ),
                    ]
                },
                {
                    "nodes": [
                        node("Family law"),
                        node("Matrimonial property act"),
                        node(
                            "accrual claim contingent until dissolution, not a proprietary right of occupation"
                        ),
                    ]
                },
            ],
        )

        html = render_to_string(
            "peachjam/judgment/_blurb_and_flynotes.html",
            {
                "document": document,
                "show_flynote_heading": True,
                "link_flynote_topics": True,
            },
        )
        normalized_html = " ".join(html.split())

        self.assertEqual(1, html.count("Family law"))
        self.assertEqual(1, html.count("Matrimonial property act"))
        self.assertIn(
            '<a href="/judgments/topics/family-law/">Family law</a>',
            normalized_html,
        )
        self.assertIn(
            '<span class="flynote-chain-tail"> '
            '<a href="/judgments/topics/matrimonial-property-act/">Matrimonial property act</a>',
            normalized_html,
        )
        self.assertIn(
            '— <a href="/judgments/topics/doctrine-of-notice-inapplicable-to-contingent-accrual-claims/">'
            "Doctrine of notice inapplicable to contingent accrual claims</a>",
            normalized_html,
        )
        self.assertIn(
            '— <a href="/judgments/topics/'
            "accrual-claim-contingent-until-dissolution,"
            '-not-a-proprietary-right-of-occupation/">'
            "accrual claim contingent until dissolution, not a proprietary right of occupation</a>",
            normalized_html,
        )
        self.assertEqual(2, html.count("<ul"))

    def test_document_table_row_renders_grouped_flynotes_without_topic_links(self):
        class EmptyRelatedManager:
            def all(self):
                return []

        def node(name):
            slug = name.lower().replace(" ", "-")
            node_obj = SimpleNamespace(name=name)
            node_obj.get_absolute_url = lambda: f"/judgments/topics/{slug}/"
            return node_obj

        document = SimpleNamespace(
            children=[],
            pk=1,
            is_group=False,
            title="Example judgment",
            get_absolute_url="/judgments/example/",
            work=SimpleNamespace(languages=[]),
            labels=EmptyRelatedManager(),
            treatments=EmptyRelatedManager(),
            doc_type="judgment",
            blurb="Appeal dismissed.",
            flynote="",
            flynote_lines=[],
            linked_flynotes=[
                {
                    "nodes": [
                        node("Family law"),
                        node("Matrimonial property act"),
                        node(
                            "Doctrine of notice inapplicable to contingent accrual claims"
                        ),
                    ]
                },
                {
                    "nodes": [
                        node("Family law"),
                        node("PIE Act"),
                        node(
                            "eviction may be just and equitable where spouse has no vested right"
                        ),
                    ]
                },
            ],
        )

        html = render_to_string(
            "peachjam/_document_table_row.html",
            {
                "document": document,
                "doc_table_toggle": False,
                "doc_table_full_title_width": False,
                "doc_table_show_treatments": False,
                "doc_table_show_citations": False,
                "doc_table_show_jurisdiction": False,
                "doc_table_show_author": False,
                "doc_table_show_court": False,
                "doc_table_show_sub_publication": False,
                "doc_table_show_frbr_uri_number": False,
                "doc_table_show_doc_type": False,
                "doc_table_show_date": False,
            },
        )
        normalized_html = " ".join(html.split())

        self.assertEqual(1, html.count("Family law"))
        self.assertNotIn("/judgments/topics/", html)
        self.assertIn("— Matrimonial property act", normalized_html)
        self.assertIn("— PIE Act", normalized_html)
        self.assertEqual(2, html.count("<ul"))

    def test_grouped_linked_flynotes_indents_children_under_compressed_topic(self):
        def node(name):
            slug = name.lower().replace(" ", "-")
            node_obj = SimpleNamespace(name=name)
            node_obj.get_absolute_url = lambda: f"/judgments/topics/{slug}/"
            return node_obj

        document = SimpleNamespace(
            blurb="Respondents liable.",
            flynote="",
            flynote_lines=[],
            linked_flynotes=[
                {
                    "nodes": [
                        node("Tort"),
                        node("Delict"),
                        node("assessment of credibility and probabilities"),
                    ]
                },
                {
                    "nodes": [
                        node("Tort"),
                        node("Delict"),
                        node("causation (but-for and legal causation)"),
                    ]
                },
            ],
        )

        html = render_to_string(
            "peachjam/judgment/_blurb_and_flynotes.html",
            {"document": document},
        )
        normalized_html = " ".join(html.split())

        self.assertIn(
            '<span class="flynote-chain-prefix"> Tort <span class="flynote-chain-separator">&nbsp;—&nbsp;</span>',
            normalized_html,
        )
        self.assertIn(
            '<span class="flynote-chain-tail"> Delict </span> '
            '<div class="flynote-chain-children"> <ul class="list-unstyled flynotes">',
            normalized_html,
        )
        self.assertIn("— assessment of credibility and probabilities", normalized_html)
        self.assertIn("— causation (but-for and legal causation)", normalized_html)

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

        self.assertGroupedFlynotesEqual(
            [
                {
                    "text": "Customs law — internal appeal jurisdiction",
                    "parts": ["Customs law", "internal appeal jurisdiction"],
                    "child_indent": 14,
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
            judgment,
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
