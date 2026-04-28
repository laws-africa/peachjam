import datetime
from io import StringIO
from unittest.mock import call, patch

from background_task.models import Task
from countries_plus.models import Country
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from languages_plus.models import Language

from peachjam.analysis.flynotes import FlynoteParser, FlynoteUpdater
from peachjam.models import Court, Judgment
from peachjam.models.flynote import Flynote, FlynoteDocumentCount, JudgmentFlynote
from peachjam.tasks import (
    FLYNOTE_REFRESH_DELAY,
    queue_refresh_flynote_document_count,
    refresh_flynote_document_count,
)


class ParseFlynoteTextTest(TestCase):
    def setUp(self):
        self.parser = FlynoteParser(assume_clean=False)

    def test_empty_input(self):
        self.assertEqual(self.parser.parse(""), [])
        self.assertEqual(self.parser.parse(None), [])

    def test_prose_flynote_skipped(self):
        text = "Contract between a lender and a borrower purporting to be a contract of sale."
        self.assertEqual(self.parser.parse(text), [])

    def test_simple_chain_with_em_dashes(self):
        text = "Criminal law \u2014 admissibility \u2014 trial within a trial"
        paths = self.parser.parse(text)
        self.assertEqual(len(paths), 1)
        self.assertEqual(
            paths[0], ["Criminal law", "admissibility", "trial within a trial"]
        )

    def test_simple_chain_with_en_dashes(self):
        text = "Employment law \u2013 Severance pay \u2013 Jurisdiction"
        paths = self.parser.parse(text)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0], ["Employment law", "Severance pay", "Jurisdiction"])

    def test_simple_chain_with_hyphens(self):
        text = "Administrative law - retrospective application - discrimination"
        paths = self.parser.parse(text)
        self.assertEqual(len(paths), 1)
        self.assertEqual(
            paths[0],
            ["Administrative law", "retrospective application", "discrimination"],
        )

    def test_semicolons_create_sibling_branches(self):
        text = "Criminal law \u2014 admissibility \u2014 trial within a trial; right to legal representation"
        paths = self.parser.parse(text)
        self.assertEqual(len(paths), 2)
        self.assertEqual(
            paths[0], ["Criminal law", "admissibility", "trial within a trial"]
        )
        self.assertEqual(
            paths[1], ["Criminal law", "admissibility", "right to legal representation"]
        )

    def test_semicolons_with_deeper_branches(self):
        text = (
            "Criminal law \u2014 admissibility \u2014 trial within a trial; "
            "circumstantial evidence \u2014 Blom principles; "
            "self-defence plea"
        )
        paths = self.parser.parse(text)
        self.assertEqual(len(paths), 3)
        self.assertEqual(
            paths[0], ["Criminal law", "admissibility", "trial within a trial"]
        )
        self.assertEqual(
            paths[1], ["Criminal law", "circumstantial evidence", "Blom principles"]
        )
        self.assertEqual(
            paths[2], ["Criminal law", "circumstantial evidence", "self-defence plea"]
        )

    def test_lowercase_semicolon_branch_keeps_existing_root(self):
        text = (
            "Criminal law \u2014 burden of proof beyond reasonable doubt; "
            "evidence \u2014 exhibits not tendered or admitted expunged; "
            "procedure \u2014 change of magistrate and I.K.S. notation; "
            "appellate review \u2014 new ground not entertained on second appeal; "
            "citation of registry not fatal"
        )
        paths = self.parser.parse(text)
        self.assertEqual(
            paths,
            [
                ["Criminal law", "burden of proof beyond reasonable doubt"],
                [
                    "Criminal law",
                    "evidence",
                    "exhibits not tendered or admitted expunged",
                ],
                [
                    "Criminal law",
                    "procedure",
                    "change of magistrate and I.K.S. notation",
                ],
                [
                    "Criminal law",
                    "appellate review",
                    "new ground not entertained on second appeal",
                ],
                ["Criminal law", "appellate review", "citation of registry not fatal"],
            ],
        )

    def test_capitalized_semicolon_branch_can_still_start_new_root(self):
        text = (
            "Criminal law \u2014 burden of proof beyond reasonable doubt; "
            "Administrative law \u2014 judicial review"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Criminal law", "burden of proof beyond reasonable doubt"],
                ["Administrative law", "judicial review"],
            ],
        )

    def test_reference_like_semicolon_branch_does_not_create_new_root(self):
        text = (
            "Criminal law \u2014 drug trafficking; "
            "No. 64/2007 \u2014 certificate of analysis"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Criminal law", "drug trafficking"],
                ["Criminal law", "No. 64/2007", "certificate of analysis"],
            ],
        )

    def test_reference_like_initial_root_is_skipped(self):
        text = "Section 18 \u2014 jurisdiction of the court"
        self.assertEqual(self.parser.parse(text), [])

    def test_semicolon_branches_stay_under_existing_area_of_law_root(self):
        text = (
            "Criminal law \u2014 guilty plea \u2014 unequivocal plea and admissions; "
            "sentencing \u2014 unnatural offence on a child under 18 \u2014 mandatory life imprisonment; "
            "appeals \u2014 enhancement of sentence"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Criminal law", "guilty plea", "unequivocal plea and admissions"],
                [
                    "Criminal law",
                    "sentencing",
                    "unnatural offence on a child under 18",
                    "mandatory life imprisonment",
                ],
                ["Criminal law", "appeals", "enhancement of sentence"],
            ],
        )

    def test_title_case_narrow_branch_does_not_start_new_root(self):
        text = (
            "Civil procedure \u2014 stay of execution; "
            "Electronic filing \u2014 late upload does not invalidate application"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Civil procedure", "stay of execution"],
                [
                    "Civil procedure",
                    "Electronic filing",
                    "late upload does not invalidate application",
                ],
            ],
        )

    def test_root_is_canonicalised_before_counting_and_branching(self):
        text = (
            "Civil Procedure \u2014 stay of execution; "
            "Civil procedure \u2014 leave to appeal"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Civil procedure", "stay of execution"],
                ["Civil procedure", "leave to appeal"],
            ],
        )

    def test_repeated_canonical_root_is_not_duplicated_in_path(self):
        text = (
            "Criminal Law \u2014 charge and conviction; "
            "Criminal law \u2014 sentence review"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Criminal law", "charge and conviction"],
                ["Criminal law", "sentence review"],
            ],
        )

    def test_single_segment_narrow_root_is_wrapped_under_broad_head(self):
        text = "Civil procedure code, order VI r.17 \u2014 amendment of pleadings"
        self.assertEqual(
            self.parser.parse(text),
            [
                [
                    "Civil procedure",
                    "Civil procedure code, order VI r.17",
                    "amendment of pleadings",
                ]
            ],
        )

    def test_multi_segment_narrow_root_is_wrapped_under_broad_head(self):
        text = (
            "Appeal \u2014 leave to appeal; jurisdiction \u2014 extension application"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Civil procedure", "Appeal", "leave to appeal"],
                ["Civil procedure", "jurisdiction", "extension application"],
            ],
        )

    def test_noncanonical_root_is_wrapped_under_canonical_head(self):
        text = "Company law \u2014 derivative action"
        self.assertEqual(
            self.parser.parse(text),
            [["Company law", "derivative action"]],
        )

    def test_legal_profession_root_is_wrapped(self):
        text = "Advocate remuneration \u2014 instruction fee"
        self.assertEqual(
            self.parser.parse(text),
            [["Legal profession", "Advocate remuneration", "instruction fee"]],
        )

    def test_evidence_root_is_wrapped(self):
        text = "Burden \u2014 proof beyond reasonable doubt"
        self.assertEqual(
            self.parser.parse(text),
            [["Evidence", "Burden", "proof beyond reasonable doubt"]],
        )

    def test_nonsense_generic_root_is_dropped(self):
        text = "National \u2014 policy \u2014 implementation"
        self.assertEqual(self.parser.parse(text), [])

    def test_road_traffic_root_is_classified_as_canonical_head(self):
        text = "Street traffic \u2014 careless driving"
        self.assertEqual(
            self.parser.parse(text),
            [["Road traffic law", "Street traffic", "careless driving"]],
        )

    def test_long_single_segment_chain_is_flattened(self):
        text = (
            "Regional integration law \u2013 EAC Treaty \u2013 rule of law \u2013 property rights "
            "\u2013 judicial review of national court decisions \u2013 international responsibility of Partner States "
            "\u2013 jurisdiction of the EACJ \u2013 time bar \u2013 res judicata \u2013 standard of proof"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Regional integration law", "EAC Treaty"],
                ["Regional integration law", "EAC Treaty", "rule of law"],
                ["Regional integration law", "EAC Treaty", "property rights"],
                [
                    "Regional integration law",
                    "EAC Treaty",
                    "judicial review of national court decisions",
                ],
                [
                    "Regional integration law",
                    "EAC Treaty",
                    "international responsibility of Partner States",
                ],
                ["Regional integration law", "EAC Treaty", "jurisdiction of the EACJ"],
                ["Regional integration law", "EAC Treaty", "time bar"],
                ["Regional integration law", "EAC Treaty", "res judicata"],
                ["Regional integration law", "EAC Treaty", "standard of proof"],
            ],
        )

    def test_root_canonicalisation_strips_leading_junk(self):
        text = '* "Civil Procedure" \u2014 stay of execution'
        self.assertEqual(
            self.parser.parse(text),
            [["Civil procedure", "stay of execution"]],
        )

    def test_statute_and_order_roots_are_not_top_level(self):
        text = (
            "Civil procedure \u2014 stay of execution; "
            "Appellate Jurisdiction Act s.5(2)(d) \u2014 leave to appeal; "
            "Advocates Remuneration Order 2015 \u2014 instruction fees"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Civil procedure", "stay of execution"],
                [
                    "Civil procedure",
                    "Appellate Jurisdiction Act s.5(2)(d)",
                    "leave to appeal",
                ],
                [
                    "Civil procedure",
                    "Advocates Remuneration Order 2015",
                    "instruction fees",
                ],
            ],
        )

    def test_institutional_and_fragment_roots_are_not_top_level(self):
        text = (
            "Land law \u2014 title dispute; "
            "Disputes Courts \u2014 jurisdiction; "
            "Cause of action \u2014 pleading requirements"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Land law", "title dispute"],
                ["Land law", "Disputes Courts", "jurisdiction"],
                ["Land law", "Cause of action", "pleading requirements"],
            ],
        )

    def test_slash_parenthetical_and_statute_fragment_roots_are_not_top_level(self):
        text = (
            "Civil procedure \u2014 stay of execution; "
            "Execution/attachment \u2014 attachment before judgment; "
            "Summary procedure (Order XXXV) \u2014 summary judgment; "
            "Probate/Administration \u2014 grant of letters; "
            "Evidence Act s.143 \u2014 corroboration not required"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Civil procedure", "stay of execution"],
                [
                    "Civil procedure",
                    "Execution/attachment",
                    "attachment before judgment",
                ],
                [
                    "Civil procedure",
                    "Summary procedure (Order XXXV)",
                    "summary judgment",
                ],
                ["Civil procedure", "Probate/Administration", "grant of letters"],
                ["Civil procedure", "Evidence Act s.143", "corroboration not required"],
            ],
        )

    def test_deeper_levels_strip_statute_tail_citations(self):
        text = "Criminal law \u2014 Evidence Act s.127(2) \u2014 child witness evidence"
        self.assertEqual(
            self.parser.parse(text),
            [["Criminal law", "Evidence", "child witness evidence"]],
        )

    def test_deeper_levels_strip_unmatched_parenthetical_suffixes(self):
        text = "Criminal law \u2014 Medical evidence (PF3 \u2014 admissibility"
        self.assertEqual(
            self.parser.parse(text),
            [["Criminal law", "Medical evidence", "admissibility"]],
        )

    def test_deeper_levels_drop_generic_noise_after_cleanup(self):
        text = "Criminal law \u2014 Procedure \u2014 change of magistrate"
        self.assertEqual(
            self.parser.parse(text),
            [["Criminal law", "change of magistrate"]],
        )

    def test_deeper_levels_drop_dangling_fragment_topics(self):
        text = "Criminal law \u2014 housebreaking and \u2014 identification evidence"
        self.assertEqual(
            self.parser.parse(text),
            [["Criminal law", "identification evidence"]],
        )

    def test_deeper_levels_drop_source_only_reference_topics(self):
        text = "Criminal law \u2014 s.127(7) evidence act \u2014 child witness evidence"
        self.assertEqual(
            self.parser.parse(text),
            [["Criminal law", "child witness evidence"]],
        )

    def test_deeper_levels_alias_pf3_and_strip_control_characters(self):
        text = "Criminal law \u2014 PF3 \u2014 Dr\x1b[118;1:3uug offences"
        self.assertEqual(
            self.parser.parse(text),
            [["Criminal law", "Medical evidence", "Drug offences"]],
        )

    def test_deeper_levels_extract_head_topic_from_citation_and_fragment_forms(self):
        text = (
            "Criminal law \u2014 Abduction under section 134 Penal Code; "
            "Criminal law \u2014 Abduction under; "
            "Criminal law \u2014 Abduction of girl under 16; "
            "Criminal law \u2014 Abduction of a girl under 16; "
            "Criminal law \u2014 Abduction (s.130(a) Penal Act"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Criminal law", "Abduction"],
                ["Criminal law", "Abduction"],
                ["Criminal law", "Abduction"],
                ["Criminal law", "Abduction"],
                ["Criminal law", "Abduction"],
            ],
        )

    def test_deeper_levels_extract_head_topic_from_comparison_and_proposition_forms(
        self,
    ):
        text = (
            "Criminal law \u2014 Burglary v. theft; "
            "Criminal law \u2014 Burglary requires proof of breaking at night; "
            "Criminal law \u2014 Burglary conviction quashed for lack of breaking; "
            "Criminal law \u2014 Burglary and armed robbery"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Criminal law", "Burglary"],
                ["Criminal law", "Burglary"],
                ["Criminal law", "Burglary"],
                ["Criminal law", "Burglary"],
            ],
        )

    def test_deeper_levels_drop_quoted_proposition_style_labels(self):
        text = (
            "Criminal law \u2014 ``sufficient cause'' not a defence; "
            "Criminal law \u2014 'armed with intent' charge"
        )
        self.assertEqual(self.parser.parse(text), [])

    def test_deeper_levels_drop_sentence_style_and_numeric_fragments(self):
        text = (
            "Criminal law \u2014 Absence of age evidence invalidates conviction; "
            "Criminal law \u2014 A court may revisit orders procured by concealment or fraud; "
            "Criminal law \u2014 229 CPA; "
            "Criminal law \u2014 12 months' imprisonment not excessive"
        )
        self.assertEqual(self.parser.parse(text), [])

    def test_deeper_levels_drop_statute_only_topics(self):
        text = (
            "Criminal law \u2014 s.127(7) evidence act; "
            "Criminal law \u2014 Section 127(2) evidence act; "
            "Criminal law \u2014 Evidence act ss.127(5), 142, 143; "
            "Criminal law \u2014 Criminal procedure act ss.378 & 379(1)"
        )
        self.assertEqual(self.parser.parse(text), [])

    def test_deeper_levels_canonicalise_common_duplicate_buckets(self):
        text = (
            "Criminal law \u2014 Fair-trial rights; "
            "Criminal law \u2014 Fair trial rights; "
            "Criminal law \u2014 Right to legal representation; "
            "Criminal law \u2014 Extra-judicial/confessional; "
            "Criminal law \u2014 Extra-judicial/confessional statements to lay persons; "
            "Criminal law \u2014 Child sexual offence; "
            "Criminal law \u2014 Child sexual offences; "
            "Criminal law \u2014 PF3/medical report; "
            "Criminal law \u2014 Robbery/armed"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Criminal law", "Fair trial"],
                ["Criminal law", "Fair trial"],
                ["Criminal law", "Fair trial"],
                ["Criminal law", "Extra-judicial confession"],
                ["Criminal law", "Extra-judicial confession"],
                ["Criminal law", "Sexual offences involving children"],
                ["Criminal law", "Sexual offences involving children"],
                ["Criminal law", "Medical evidence"],
                ["Criminal law", "Armed robbery"],
            ],
        )

    def test_deeper_levels_drop_generic_stub_topics(self):
        text = (
            "Criminal law \u2014 Proof; "
            "Criminal law \u2014 Requirement; "
            "Criminal law \u2014 Standard; "
            "Criminal law \u2014 Unlawful"
        )
        self.assertEqual(self.parser.parse(text), [])

    def test_deeper_levels_canonicalise_revision_search_and_right_variants(self):
        text = (
            "Criminal law \u2014 Revision application; "
            "Criminal law \u2014 Revisional powers under s.4(2) AJA; "
            "Criminal law \u2014 Search without warrant; "
            "Criminal law \u2014 Seizure certificate vs receipt (s.38(3) CPA; "
            "Criminal law \u2014 Right to cross-examination; "
            "Criminal law \u2014 Right to interpretation"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Criminal law", "Revision"],
                ["Criminal law", "Revision"],
                ["Criminal law", "Search and seizure"],
                ["Criminal law", "Search and seizure"],
                ["Criminal law", "Fair trial"],
                ["Criminal law", "Fair trial"],
            ],
        )

    def test_deeper_levels_canonicalise_identification_and_trial_variants(self):
        text = (
            "Criminal law \u2014 Identification procedures; "
            "Criminal law \u2014 Identification parades; "
            "Criminal law \u2014 Identification parade collateral; "
            "Criminal law \u2014 Identification evidence in night-time offences; "
            "Criminal law \u2014 Trial in absentia after accused absconds; "
            "Criminal law \u2014 Trial-within-trial procedure; "
            "Criminal law \u2014 Unsafe convictions"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Criminal law", "Identification"],
                ["Criminal law", "Identification parade"],
                ["Criminal law", "Identification parade"],
                ["Criminal law", "Visual identification"],
                ["Criminal law", "Trial in absentia"],
                ["Criminal law", "Trial-within-trial"],
                ["Criminal law", "Unsafe conviction"],
            ],
        )

    def test_deeper_levels_drop_more_section_and_holding_fragments(self):
        text = (
            "Criminal law \u2014 s.383; "
            "Criminal law \u2014 Rule 75; "
            "Criminal law \u2014 Section 231(1) CPA is mandatory; "
            "Criminal law \u2014 4) stolen item must be subject of charge"
        )
        self.assertEqual(self.parser.parse(text), [])

    def test_deeper_levels_drop_statute_title_noise_and_map_safe_topic_forms(self):
        text = (
            "Criminal law \u2014 The Nairobi Municipality (Amendment) By-laws 1944-11j-1aw 212; "
            "Criminal law \u2014 The Defence (Sale; "
            "Criminal law \u2014 The defence (control; "
            "Criminal law \u2014 The graver offence prevails; "
            "Criminal law \u2014 Test is whether a prima facie case exists"
        )
        self.assertEqual(self.parser.parse(text), [])

    def test_deeper_levels_drop_article_currency_and_numeric_reference_noise(self):
        text = (
            "Criminal law \u2014 Article 108(2) constitution; "
            "Criminal law \u2014 Tzs.1,000,000/= bond; "
            "Criminal law \u2014 371(1)(a) criminal procedure act; "
            "Criminal law \u2014 12 months' imprisonment not excessive"
        )
        self.assertEqual(self.parser.parse(text), [])

    def test_single_segment_numeric_and_article_roots_do_not_wrap_under_classified_root(
        self,
    ):
        text = (
            "388 CPA cannot cure jurisdictional defect; "
            "31 evidence act; "
            "295; "
            "Article 108(2) constitution; "
            "Tzs.1,000,000/= bond"
        )
        self.assertEqual(self.parser.parse(text), [])

    def test_semicolon_branches_do_not_promote_numeric_noise_to_second_level(self):
        text = (
            "Criminal law \u2014 admissibility; "
            "388 CPA cannot cure jurisdictional defect; "
            "295; "
            "30-year sentence upheld; "
            "Article 108(2) constitution; "
            "Tzs.1,000,000/= bond"
        )
        self.assertEqual(
            self.parser.parse(text),
            [["Criminal law", "admissibility"]],
        )

    def test_deeper_levels_map_statute_decorated_topic_labels_to_safe_heads(self):
        text = (
            "Criminal law \u2014 Magistrates' courts act s44(1)(b) and civil procedure code; "
            "Criminal law \u2014 Magistrates courts act s.20(3),(4; "
            "Criminal law \u2014 Incest (s.158(1)(a) Penal Code; "
            "Criminal law \u2014 Revisional jurisdiction (s.37(1) Criminal Procedure Code; "
            "Criminal law \u2014 Attempted rape (s.132(1)"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Criminal law", "Magistrates' courts"],
                ["Criminal law", "Magistrates' courts"],
                ["Criminal law", "Incest"],
                ["Criminal law", "Revision"],
                ["Criminal law", "Attempted rape"],
            ],
        )

    def test_deeper_levels_group_safe_arson_and_police_variants(self):
        text = (
            "Criminal law \u2014 Arson/offences relating to setting fire; "
            "Criminal law \u2014 Arson/destruction; "
            "Criminal law \u2014 arson, burglary; "
            "Criminal law \u2014 Arson (s. 519(a) Penal Code; "
            "Criminal law \u2014 Police/anti-corruption squad conduct; "
            "Criminal law \u2014 Police procedure; "
            "Criminal law \u2014 Police powers; "
            "Criminal law \u2014 Police-station identifications versus in-court identification; "
            "Criminal law \u2014 Police identification"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Criminal law", "Arson"],
                ["Criminal law", "Arson"],
                ["Criminal law", "Arson"],
                ["Criminal law", "Arson"],
                ["Criminal law", "Police procedure"],
                ["Criminal law", "Police procedure"],
                ["Criminal law", "Police procedure"],
                ["Criminal law", "Identification"],
                ["Criminal law", "Identification"],
            ],
        )

    def test_deeper_levels_strip_numbered_list_markers_and_curly_quotes(self):
        text = (
            "Criminal law \u2014 4) stolen thing in accused's possession is subject of the charge; "
            "Criminal law \u2014 2) property positively the complainant's; "
            "Criminal law \u2014 ``sufficient cause''; "
            "Criminal law \u2014 \u201clegal personality\u201d not a defence"
        )
        self.assertEqual(self.parser.parse(text), [])

    def test_rule_and_dangling_fragment_roots_are_not_top_level(self):
        text = (
            "Civil procedure \u2014 stay of execution; "
            "Order XXI Rule 39 \u2014 execution pending appeal; "
            "Arbitration & \u2014 stay of proceedings; "
            "Republic) \u2014 public law point"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Civil procedure", "stay of execution"],
                ["Civil procedure", "Order XXI Rule 39", "execution pending appeal"],
                ["Civil procedure", "Arbitration &", "stay of proceedings"],
                ["Civil procedure", "Republic)", "public law point"],
            ],
        )

    def test_prose_like_roots_are_not_top_level(self):
        text = (
            "Criminal law \u2014 charge and conviction; "
            "appeal lodged without leave incompetent \u2014 striking out; "
            "mandatory requirement to record assessors' opinions \u2014 departure invalid"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Criminal law", "charge and conviction"],
                [
                    "Criminal law",
                    "appeal lodged without leave incompetent",
                    "striking out",
                ],
                [
                    "Criminal law",
                    "mandatory requirement to record assessors' opinions",
                    "departure invalid",
                ],
            ],
        )

    def test_slash_act_section_and_holding_roots_are_not_top_level(self):
        text = (
            "Civil procedure \u2014 stay of execution; "
            "Civil procedure/material law \u2014 overlap of remedies; "
            "Evidence Act, s.123 \u2014 corroboration rule; "
            "absence of assessors' opinions on record is a serious irregularity rendering proceedings nullity "
            "\u2014 conviction unsafe"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Civil procedure", "stay of execution"],
                [
                    "Civil procedure",
                    "Civil procedure/material law",
                    "overlap of remedies",
                ],
                ["Civil procedure", "Evidence Act, s.123", "corroboration rule"],
                [
                    "Civil procedure",
                    "absence of assessors' opinions on record is a serious irregularity rendering proceedings nullity",
                    "conviction unsafe",
                ],
            ],
        )

    def test_dangling_rules_and_labour_fragments_are_not_top_level(self):
        text = (
            "Employment law \u2014 unfair dismissal; "
            "Labour Relations Act) \u2014 collective bargaining; "
            "No. 42 of 2007, Rules 13 & 14 and \u2014 filing requirements; "
            "Guidelines) \u2014 compliance; "
            "Labour practice \u2014 disciplinary code; "
            "absence of compliant affidavit renders application incompetent \u2014 striking out"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Employment law", "unfair dismissal"],
                ["Employment law", "Labour Relations Act)", "collective bargaining"],
                [
                    "Employment law",
                    "No. 42 of 2007, Rules 13 & 14 and",
                    "filing requirements",
                ],
                ["Employment law", "Guidelines)", "compliance"],
                ["Employment law", "Labour practice", "disciplinary code"],
                [
                    "Employment law",
                    "absence of compliant affidavit renders application incompetent",
                    "striking out",
                ],
            ],
        )

    def test_rule_section_cap_and_generic_procedural_roots_are_not_top_level(self):
        text = (
            "Civil procedure \u2014 stay of execution; "
            "Order XXI Rule 10 \u2014 execution mechanics; "
            "Companies Act, Cap 212 \u2014 minority protection; "
            "Use of section 95 CPC \u2014 inherent powers; "
            "Evidentiary value of PF3 \u2014 proof of injuries"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Civil procedure", "stay of execution"],
                ["Civil procedure", "Order XXI Rule 10", "execution mechanics"],
                ["Civil procedure", "Companies Act, Cap 212", "minority protection"],
                ["Civil procedure", "Use of section 95 CPC", "inherent powers"],
                ["Civil procedure", "Evidentiary value of PF3", "proof of injuries"],
            ],
        )

    def test_non_latin_numeric_fact_and_rule_date_roots_are_not_top_level(self):
        text = (
            "Criminal law \u2014 drug trafficking; "
            "\u062d\u0642\u0648\u0642 \u0627\u0644\u0625\u0646\u0633\u0627\u0646 \u2014 fair trial rights; "
            "174.77 kg heroin seized \u2014 evidential weight; "
            ". 1927, Order 19, Rule 63 \u2014 procedural history"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Criminal law", "drug trafficking"],
                [
                    "Criminal law",
                    "\u062d\u0642\u0648\u0642 \u0627\u0644\u0625\u0646\u0633\u0627\u0646",
                    "fair trial rights",
                ],
                ["Criminal law", "174.77 kg heroin seized", "evidential weight"],
                ["Criminal law", ". 1927, Order 19, Rule 63", "procedural history"],
            ],
        )

    def test_broad_area_roots_are_not_treated_as_prose_fragments(self):
        text = (
            "Election law \u2014 inspection of documents\n"
            "Civil procedure \u2014 stay of execution\n"
            "Criminal law \u2014 charge and conviction"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                ["Election law", "inspection of documents"],
                ["Civil procedure", "stay of execution"],
                ["Criminal law", "charge and conviction"],
            ],
        )

    def test_full_spec_example(self):
        text = (
            "Criminal law \u2014 admissibility of confessions/ admissions \u2014 "
            "trial within a trial where voluntariness or infringement of rights disputed; "
            "right to legal representation when statement taken; "
            "circumstantial evidence \u2014 Blom and Chabalala principles; "
            "self-defence plea and evidential burden; "
            "appellate review of factual findings."
        )
        paths = self.parser.parse(text)
        self.assertEqual(len(paths), 5)
        self.assertEqual(paths[0][0], "Criminal law")
        self.assertEqual(paths[0][1], "admissibility of confessions/ admissions")
        self.assertEqual(
            paths[1][-1], "right to legal representation when statement taken"
        )
        self.assertEqual(paths[2][1], "circumstantial evidence")
        self.assertEqual(paths[2][2], "Blom and Chabalala principles")
        self.assertEqual(paths[3][-1], "self-defence plea and evidential burden")
        self.assertEqual(paths[4][-1], "appellate review of factual findings")

    def test_semicolons_inside_parentheses_not_split(self):
        """Semicolons inside (...) should NOT create sibling branches."""
        text = (
            "Labour law \u2013 Mediation irregularities "
            "(change of mediators; confidentiality; 30-day limit) "
            "\u2013 Arbitration independent of mediation; "
            "Termination of employment \u2013 substantive fairness \u2013 "
            "termination letter must reflect charge; "
            "employer\u2019s burden to prove fairness under ELRA"
        )
        paths = self.parser.parse(text)
        self.assertEqual(len(paths), 3)
        # First path keeps the parenthetical intact
        self.assertEqual(
            paths[0],
            [
                "Labour law",
                "Mediation irregularities "
                "(change of mediators; confidentiality; 30-day limit)",
                "Arbitration independent of mediation",
            ],
        )
        # Second path is a sibling branch (semicolon outside parens)
        self.assertEqual(paths[1][0], "Termination of employment")
        self.assertEqual(paths[1][1], "substantive fairness")
        self.assertEqual(paths[1][2], "termination letter must reflect charge")
        # Third path
        self.assertEqual(
            paths[2][-1], "employer\u2019s burden to prove fairness under ELRA"
        )

    def test_semicolons_inside_nested_parentheses(self):
        """Semicolons inside nested brackets should not split."""
        text = "Tax law \u2014 exemptions (see also (a; b; c)) \u2014 compliance"
        paths = self.parser.parse(text)
        self.assertEqual(len(paths), 1)
        self.assertEqual(
            paths[0],
            ["Tax law", "exemptions (see also (a; b; c))", "compliance"],
        )

    def test_dashes_inside_parentheses_do_not_create_new_levels(self):
        text = (
            "Civil procedure \u2014 Extension of time to challenge arbitral award "
            "\u2014 Application under Limitation Act sections 14 and 21(2) "
            "\u2014 Lyamuya criteria (accounting for delay, inordinate delay, diligence, other sufficient reasons) "
            "\u2014 Illegality apparent on face of record (Arbitration Act s.59(2)(c) \u2014 seat of arbitration) "
            "can constitute good cause \u2014 Court will not determine substantive merits in extension application"
        )
        paths = self.parser.parse(text)
        self.assertEqual(len(paths), 1)
        self.assertEqual(
            paths[0],
            [
                "Civil procedure",
                "Extension of time to challenge arbitral award",
                "Application under Limitation Act sections 14 and 21(2)",
                "Lyamuya criteria (accounting for delay, inordinate delay, diligence, other sufficient reasons)",
                "Illegality apparent on face of record (Arbitration Act s.59(2)(c) "
                "— seat of arbitration) can constitute good cause",
                "Court will not determine substantive merits in extension application",
            ],
        )

    def test_trailing_period_stripped(self):
        text = "Employment law \u2013 Severance pay."
        paths = self.parser.parse(text)
        self.assertEqual(paths[0][-1], "Severance pay")

    def test_clean_strips_leading_unicode_hyphens(self):
        text = "\u2014 Criminal law \u2014 admissibility \u2014 trial within a trial"
        self.assertEqual(
            self.parser.parse(text),
            [["Criminal law", "admissibility", "trial within a trial"]],
        )

    def test_newlines_start_new_flynotes(self):
        text = (
            "Criminal law \u2014 admissibility \u2014 trial within a trial\n"
            "Administrative law \u2014 judicial review"
        )
        paths = self.parser.parse(text)
        self.assertEqual(
            paths,
            [
                ["Criminal law", "admissibility", "trial within a trial"],
                ["Administrative law", "judicial review"],
            ],
        )

    def test_normalise_multiline_text_preserves_existing_lines(self):
        text = (
            "Criminal law \u2014 admissibility \u2014 trial within a trial\n"
            "Administrative law \u2014 judicial review"
        )
        self.assertEqual(self.parser.normalise_multiline_text(text), text)

    def test_normalise_multiline_text_splits_repeated_sentence_flynotes(self):
        text = (
            "Contract - Contract of sale of goods - Whether and under what circumstances "
            "a mere purchase order may amount to an agreement to sell. "
            "Contract - Contract of sale of goods - Delivery - Mode of delivery - "
            "Agreement is silent on mode of delivery - Delivery in one lot presumed."
        )
        self.assertEqual(
            self.parser.normalise_multiline_text(text),
            (
                "Contract - Contract of sale of goods - Whether and under what circumstances "
                "a mere purchase order may amount to an agreement to sell\n"
                "Contract - Contract of sale of goods - Delivery - Mode of delivery - "
                "Agreement is silent on mode of delivery - Delivery in one lot presumed"
            ),
        )

    def test_normalise_multiline_text_splits_sentence_case_topic_restarts(self):
        text = (
            "Arbitration - Arbitration clause in a contract - Whether such an arbitration clause can operate "
            "to oust the jurisdiction of the Courts. "
            "Civil practice and procedure - Preliminary point of objection - Whether such objection can be sustained. "
            "Civil practice and procedure - Arbitration clause - Party filing a suit in court in defiance of an "
            "arbitration clause"
        )
        self.assertEqual(
            self.parser.normalise_multiline_text(text),
            (
                "Arbitration - Arbitration clause in a contract - Whether such an arbitration clause can operate "
                "to oust the jurisdiction of the Courts\n"
                "Civil practice and procedure - Preliminary point of objection - "
                "Whether such objection can be sustained\n"
                "Civil practice and procedure - Arbitration clause - Party filing a suit in court in defiance of an "
                "arbitration clause"
            ),
        )

    def test_normalise_multiline_text_does_not_split_mid_path_title_phrase(self):
        text = (
            "Civil practice and procedure - Preliminary point of objection - Parties subjecting themselves "
            "exclusively to the jurisdiction of the Kenya Courts - Objection to Tanzania Courts' having "
            "jurisdiction - Whether such objection can be sustained. "
            "Civil practice and procedure - Arbitration clause - Party filing a suit in court in defiance of "
            "an arbitration clause"
        )
        self.assertEqual(
            self.parser.normalise_multiline_text(text),
            (
                "Civil practice and procedure - Preliminary point of objection - Parties subjecting themselves "
                "exclusively to the jurisdiction of the Kenya Courts - Objection to Tanzania Courts' having "
                "jurisdiction - Whether such objection can be sustained\n"
                "Civil practice and procedure - Arbitration clause - Party filing a suit in court in defiance of "
                "an arbitration clause"
            ),
        )

    def test_normalise_multiline_text_splits_embedded_topic_restarts(self):
        text = (
            "Land Law - Acquisition of Title to Land - Whether the title is valid "
            "Judicial Notice - Explanatory Notes to subsidiary legislation "
            "Land Law - Possession of land - Whether that owner is in possession "
            "Trespass - Trespass to land - Whether it is intrusion upon land in the possession of another "
            "Damages - Damages for trespass - Damages payable without proof of actual loss or damage"
        )
        self.assertEqual(
            self.parser.normalise_multiline_text(text),
            (
                "Land Law - Acquisition of Title to Land - Whether the title is valid\n"
                "Judicial Notice - Explanatory Notes to subsidiary legislation\n"
                "Land Law - Possession of land - Whether that owner is in possession\n"
                "Trespass - Trespass to land - Whether it is intrusion upon land in the possession of another\n"
                "Damages - Damages for trespass - Damages payable without proof of actual loss or damage"
            ),
        )

    def test_parse_splits_hidden_restarts_without_punctuation(self):
        text = (
            "Land Law - Acquisition of Title to Land - Whether the title is valid "
            "Judicial Notice - Explanatory Notes to subsidiary legislation "
            "Land Law - Possession of land - Whether that owner is in possession "
            "Trespass - Trespass to land - Whether it is intrusion upon land in the possession of another "
            "Damages - Damages for trespass - Damages payable without proof of actual loss or damage"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                [
                    "Land Law",
                    "Acquisition of Title to Land",
                    "Whether the title is valid",
                ],
                ["Judicial Notice", "Explanatory Notes to subsidiary legislation"],
                [
                    "Land Law",
                    "Possession of land",
                    "Whether that owner is in possession",
                ],
                [
                    "Trespass",
                    "Trespass to land",
                    "Whether it is intrusion upon land in the possession of another",
                ],
                [
                    "Damages",
                    "Damages for trespass",
                    "Damages payable without proof of actual loss or damage",
                ],
            ],
        )

    def test_normalise_multiline_text_strips_held_section(self):
        text = (
            "Contract - Contract of sale of goods - Delivery - Mode of delivery. "
            "Held: (i) The buyer was at liberty to rescind the contract."
        )
        self.assertEqual(
            self.parser.normalise_multiline_text(text),
            "Contract - Contract of sale of goods - Delivery - Mode of delivery",
        )

    def test_normalise_multiline_text_removes_report_markers_and_dedupes(self):
        text = (
            "A Contract - Contract of sale of goods - Delivery - Mode of delivery. "
            "Contract - Contract of sale of goods - Delivery - Mode of delivery."
        )
        self.assertEqual(
            self.parser.normalise_multiline_text(text),
            "Contract - Contract of sale of goods - Delivery - Mode of delivery",
        )

    def test_parse_repeated_sentence_flynotes_as_separate_paths(self):
        text = (
            "Contract - Contract of sale of goods - Whether and under what circumstances "
            "a mere purchase order may amount to an agreement to sell. "
            "Contract - Contract of sale of goods - Rules governing delivery of goods - "
            "Whether Buyer is bound to accept delivery in instalments."
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                [
                    "Contract",
                    "Contract of sale of goods",
                    "Whether and under what circumstances a mere purchase order may amount to an agreement to sell",
                ],
                [
                    "Contract",
                    "Contract of sale of goods",
                    "Rules governing delivery of goods",
                    "Whether Buyer is bound to accept delivery in instalments",
                ],
            ],
        )

    def test_normalise_multiline_text_splits_mid_line_topic_restarts(self):
        text = (
            "Civil Practice and Procedure - Proceedings against a corporate body - "
            "Court action against the decision of a meeting of an organ of a cooperative union - "
            "Whether proceedings may be instituted against that particular organ "
            "Civil Practice and Procedure - Non-joinder of parties - Whether an essential "
            "party not joined to an action may be joined at the stage of formulating the judgment - "
            "Order I rule 10(2) of the Civil Procedure Code 1966 "
            "Administrative Law - Jurisdiction of an administrative body - Requirement of quorum - "
            "Whether the meeting had jurisdiction to make valid decisions"
        )
        self.assertEqual(
            self.parser.normalise_multiline_text(text),
            (
                "Civil Practice and Procedure - Proceedings against a corporate body - "
                "Court action against the decision of a meeting of an organ of a cooperative union - "
                "Whether proceedings may be instituted against that particular organ\n"
                "Civil Practice and Procedure - Non-joinder of parties - Whether an essential "
                "party not joined to an action may be joined at the stage of formulating the judgment - "
                "Order I rule 10(2) of the Civil Procedure Code 1966\n"
                "Administrative Law - Jurisdiction of an administrative body - Requirement of quorum - "
                "Whether the meeting had jurisdiction to make valid decisions"
            ),
        )

    def test_parse_mid_line_topic_restarts_as_separate_paths(self):
        text = (
            "Civil Practice and Procedure - Proceedings against a corporate body - "
            "Whether proceedings may be instituted against that particular organ "
            "Administrative Law - Jurisdiction of an administrative body - Requirement of quorum - "
            "Whether the meeting had jurisdiction to make valid decisions"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                [
                    "Civil Practice and Procedure",
                    "Proceedings against a corporate body",
                    "Whether proceedings may be instituted against that particular organ",
                ],
                [
                    "Administrative Law",
                    "Jurisdiction of an administrative body",
                    "Requirement of quorum",
                    "Whether the meeting had jurisdiction to make valid decisions",
                ],
            ],
        )

    def test_parse_multiline_clean_flynotes_do_not_use_restart_inference(self):
        parser = FlynoteParser(assume_clean=True)
        text = (
            "Contract - Contract of sale of goods - Whether and under what circumstances "
            "a mere purchase order may amount to an agreement to sell. Contract\n"
            "Administrative Law - Jurisdiction of an administrative body - Requirement of quorum - "
            "Whether the meeting had jurisdiction to make valid decisions"
        )
        self.assertEqual(
            parser.parse(text),
            [
                [
                    "Contract",
                    "Contract of sale of goods",
                    (
                        "Whether and under what circumstances a mere purchase order may amount to an agreement to "
                        "sell. Contract"
                    ),
                ],
                [
                    "Administrative Law",
                    "Jurisdiction of an administrative body",
                    "Requirement of quorum",
                    "Whether the meeting had jurisdiction to make valid decisions",
                ],
            ],
        )

    def test_parse_stops_before_statute_reference_tail(self):
        text = (
            "Jurisdiction - Buganda courts - Suit for damages - Car collision - "
            "Both parties Africans - Suit filed in the High Court - "
            "Submission on appeal that case should have been transferred to Buganda court - "
            "Jurisdiction of High Court - When High Court must transfer case to Buganda court - "
            "Civil Procedure Rules, O. 9, r. 24 and O. 42 (U.) - "
            "Civil Procedure Ordinance, s. 11 (7) and s. 69 (1) (U.)"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                [
                    "Jurisdiction",
                    "Buganda courts",
                    "Suit for damages",
                    "Car collision",
                    "Both parties Africans",
                    "Suit filed in the High Court",
                    "Submission on appeal that case should have been transferred to Buganda court",
                    "Jurisdiction of High Court",
                    "When High Court must transfer case to Buganda court",
                ]
            ],
        )

    def test_reference_tail_preserves_issue_statement_with_section(self):
        text = (
            "Natural Justice - Right to be heard - "
            "Whether that failure amounts to forfeiture of the Committee's right to be heard - "
            "Section 106 of the Cooperative Societies Act 1982"
        )
        self.assertEqual(
            self.parser.parse(text),
            [
                [
                    "Natural Justice",
                    "Right to be heard",
                    "Whether that failure amounts to forfeiture of the Committee's right to be heard",
                ]
            ],
        )


class NormaliseFlynoteNameTest(TestCase):
    def test_basic_normalisation(self):
        self.assertEqual(FlynoteParser.normalise_name("Criminal Law"), "criminal-law")

    def test_strips_whitespace(self):
        self.assertEqual(
            FlynoteParser.normalise_name("  Criminal Law  "), "criminal-law"
        )

    def test_consistent_slugs(self):
        self.assertEqual(
            FlynoteParser.normalise_name("Right to fair hearing"),
            FlynoteParser.normalise_name("right to fair hearing"),
        )

    def test_canonicalises_root_name(self):
        self.assertEqual(
            FlynoteParser.canonicalise_root_name('* "Civil Procedure"'),
            "Civil procedure",
        )

    def test_classifies_generic_root(self):
        self.assertEqual(
            FlynoteParser.classify_top_level_root("Civil Procedure"),
            "Civil procedure",
        )
        self.assertEqual(
            FlynoteParser.classify_top_level_root("Sentencing"),
            "Criminal law",
        )

    def test_rejects_authority_and_citation_style_roots(self):
        self.assertTrue(
            FlynoteParser._looks_like_bad_top_level_root(
                "Authorities: bushiri amiri v r"
            )
        )
        self.assertTrue(FlynoteParser._looks_like_bad_top_level_root("Article 107A"))
        self.assertTrue(FlynoteParser._looks_like_bad_top_level_root("Read with s43"))

    def test_infers_remaining_narrow_heads(self):
        self.assertEqual(
            FlynoteParser.infer_top_level_root("Road/transport law"),
            "Road traffic law",
        )
        self.assertEqual(
            FlynoteParser.infer_top_level_root("Public corporations"),
            "Administrative law",
        )
        self.assertEqual(
            FlynoteParser.infer_top_level_root("Murder"),
            "Criminal law",
        )


class GetOrCreateFlynoteNodeTest(TestCase):
    def setUp(self):
        self.updater = FlynoteUpdater()

    def test_creates_new_top_level(self):
        node = self.updater.get_or_create_node(None, "Criminal law")
        self.assertIsNotNone(node)
        self.assertEqual(node.name, "Criminal law")
        self.assertTrue(node.is_root())

    def test_returns_existing_by_normalised_root_name(self):
        Flynote.add_root(name="Criminal law")
        found = self.updater.get_or_create_node(None, "Criminal law")
        self.assertEqual(Flynote.objects.filter(name="Criminal law").count(), 1)
        self.assertEqual(found.name, "Criminal law")

    def test_returns_existing_by_normalised_name(self):
        Flynote.add_root(name="Criminal Law")
        found = self.updater.get_or_create_node(None, "criminal law")
        self.assertEqual(found.name, "Criminal Law")

    def test_caches_nodes_by_parent_and_normalised_name(self):
        found = self.updater.get_or_create_node(None, "Criminal law")
        self.assertEqual(self.updater.node_cache[(None, "criminal-law")].pk, found.pk)

        again = self.updater.get_or_create_node(None, "Criminal law")
        self.assertEqual(again.pk, found.pk)

    def test_creates_nested_nodes(self):
        parent = self.updater.get_or_create_node(None, "Criminal law")
        child = self.updater.get_or_create_node(parent, "admissibility")
        self.assertIsNotNone(child)
        self.assertFalse(child.is_root())
        self.assertEqual(child.get_parent().pk, parent.pk)


class UpdateFlynoteForJudgmentTest(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.updater = FlynoteUpdater()

        self.judgment = Judgment.objects.create(
            case_name="Test Case",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
            flynote_raw=(
                "Criminal law \u2014 admissibility \u2014 trial within a trial"
                "; circumstantial evidence \u2014 Blom principles"
            ),
        )

    def test_creates_flynote_nodes(self):
        self.updater.update_for_judgment(self.judgment)

        self.assertTrue(Flynote.objects.filter(name="Criminal law").exists())
        self.assertTrue(Flynote.objects.filter(name="admissibility").exists())
        self.assertTrue(Flynote.objects.filter(name="trial within a trial").exists())
        self.assertTrue(Flynote.objects.filter(name="circumstantial evidence").exists())
        self.assertTrue(Flynote.objects.filter(name="Blom principles").exists())

    def test_links_judgment_to_leaf_nodes_only(self):
        self.updater.update_for_judgment(self.judgment)

        linked_flynotes = set(
            JudgmentFlynote.objects.filter(document=self.judgment).values_list(
                "flynote__name", flat=True
            )
        )
        self.assertIn("trial within a trial", linked_flynotes)
        self.assertIn("Blom principles", linked_flynotes)
        self.assertNotIn("Criminal law", linked_flynotes)
        self.assertNotIn("admissibility", linked_flynotes)
        self.assertNotIn("circumstantial evidence", linked_flynotes)

    def test_flynote_tree_structure(self):
        self.updater.update_for_judgment(self.judgment)

        criminal = Flynote.objects.get(name="Criminal law")
        self.assertTrue(criminal.is_root())

        admissibility = Flynote.objects.get(name="admissibility")
        self.assertEqual(admissibility.get_parent().pk, criminal.pk)

        trial = Flynote.objects.get(name="trial within a trial")
        self.assertEqual(trial.get_parent().pk, admissibility.pk)

    def test_clears_old_links_on_reprocess(self):
        self.updater.update_for_judgment(self.judgment)
        initial_count = JudgmentFlynote.objects.filter(document=self.judgment).count()
        self.assertEqual(initial_count, 2)

        self.judgment.flynote_raw = "Contract law \u2014 breach of contract"
        self.judgment.save()
        self.updater.update_for_judgment(self.judgment)

        linked_flynotes = set(
            JudgmentFlynote.objects.filter(document=self.judgment).values_list(
                "flynote__name", flat=True
            )
        )
        self.assertEqual(linked_flynotes, {"breach of contract"})

    def test_reuses_existing_flynote_nodes(self):
        self.updater.update_for_judgment(self.judgment)
        criminal_pk = Flynote.objects.get(name="Criminal law").pk

        judgment2 = Judgment.objects.create(
            case_name="Test Case 2",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 2, 1),
            language=Language.objects.first(),
            flynote_raw="Criminal law \u2014 sentencing",
        )
        self.updater.update_for_judgment(judgment2)

        self.assertEqual(Flynote.objects.filter(name="Criminal law").count(), 1)
        self.assertEqual(Flynote.objects.get(name="Criminal law").pk, criminal_pk)

    def test_empty_flynote_skips(self):
        self.judgment.flynote_raw = ""
        self.judgment.save()

        self.updater.update_for_judgment(self.judgment)
        self.assertEqual(
            JudgmentFlynote.objects.filter(document=self.judgment).count(), 0
        )

    def test_prose_flynote_skips(self):
        self.judgment.flynote_raw = "This is a plain prose description of the case."
        self.judgment.save()

        self.updater.update_for_judgment(self.judgment)
        self.assertEqual(
            JudgmentFlynote.objects.filter(document=self.judgment).count(), 0
        )

    def test_multiline_flynotes_link_separate_leaf_nodes(self):
        self.judgment.flynote_raw = (
            "Criminal law \u2014 admissibility \u2014 trial within a trial\n"
            "Administrative law \u2014 judicial review"
        )
        self.judgment.save()

        self.updater.update_for_judgment(self.judgment)

        linked_flynotes = set(
            JudgmentFlynote.objects.filter(document=self.judgment).values_list(
                "flynote__name", flat=True
            )
        )
        self.assertEqual(linked_flynotes, {"trial within a trial", "judicial review"})

    def test_refresh_counts_queues_delayed_refresh_per_root(self):
        with (
            patch.object(
                self.updater.parser,
                "parse",
                return_value=[
                    ["Criminal law", "admissibility", "trial within a trial"],
                    ["Administrative law", "judicial review"],
                ],
            ),
            patch(
                "peachjam.analysis.flynotes.queue_refresh_flynote_document_count"
            ) as mock_refresh,
        ):
            self.updater.update_for_judgment(self.judgment, refresh_counts=True)

        admin = Flynote.objects.get(name="Administrative law")
        criminal = Flynote.objects.get(name="Criminal law")
        self.assertCountEqual(
            mock_refresh.call_args_list,
            [
                call(admin.pk),
                call(criminal.pk),
            ],
        )

    def test_refresh_counts_queues_once_for_shared_root(self):
        with patch(
            "peachjam.analysis.flynotes.queue_refresh_flynote_document_count"
        ) as mock_refresh:
            self.updater.update_for_judgment(self.judgment, refresh_counts=True)

        criminal = Flynote.objects.get(name="Criminal law")
        mock_refresh.assert_called_once_with(criminal.pk)


class QueueRefreshFlynoteDocumentCountTest(TestCase):
    def setUp(self):
        Task.objects.all().delete()

    def test_queue_refresh_schedules_for_24_hours(self):
        before = timezone.now()

        task = queue_refresh_flynote_document_count(123)

        self.assertEqual(task.task_name, refresh_flynote_document_count.name)
        self.assertGreaterEqual(
            task.run_at,
            before + datetime.timedelta(seconds=FLYNOTE_REFRESH_DELAY - 60),
        )

    def test_queue_refresh_keeps_existing_pending_task(self):
        first_task = queue_refresh_flynote_document_count(123)
        second_task = queue_refresh_flynote_document_count(123)

        self.assertEqual(first_task.pk, second_task.pk)
        self.assertEqual(
            Task.objects.filter(
                task_name=refresh_flynote_document_count.name,
            ).count(),
            1,
        )


class FlynoteDocumentCountTest(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.updater = FlynoteUpdater()

    def test_refresh_populates_counts_for_top_level_topics(self):
        judgment = Judgment.objects.create(
            case_name="Count Test",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
            flynote_raw="Criminal law \u2014 admissibility",
        )
        self.updater.update_for_judgment(judgment)
        criminal = Flynote.objects.get(name="Criminal law")
        FlynoteDocumentCount.refresh_for_flynote(criminal)

        count_row = FlynoteDocumentCount.objects.get(flynote=criminal)
        self.assertEqual(count_row.count, 1)

    def test_ancestor_count_includes_descendant_documents(self):
        judgment1 = Judgment.objects.create(
            case_name="Case 1",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
            flynote_raw="Criminal law \u2014 admissibility \u2014 trial within a trial",
        )
        judgment2 = Judgment.objects.create(
            case_name="Case 2",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 2, 1),
            language=Language.objects.first(),
            flynote_raw="Criminal law \u2014 sentencing",
        )
        self.updater.update_for_judgment(judgment1)
        self.updater.update_for_judgment(judgment2)
        criminal = Flynote.objects.get(name="Criminal law")
        FlynoteDocumentCount.refresh_for_flynote(criminal)

        count_row = FlynoteDocumentCount.objects.get(flynote=criminal)
        self.assertEqual(count_row.count, 2)

    def test_refresh_for_all_flynotes_updates_all(self):
        """refresh_for_all_flynotes() updates counts for all flynotes in one go."""
        FlynoteDocumentCount.refresh_for_all_flynotes()
        self.assertEqual(FlynoteDocumentCount.objects.count(), 0)

        judgment = Judgment.objects.create(
            case_name="All Refresh Test",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
            flynote_raw="Criminal law \u2014 admissibility",
        )
        self.updater.update_for_judgment(judgment)
        FlynoteDocumentCount.refresh_for_all_flynotes()
        criminal = Flynote.objects.get(name="Criminal law")
        count_row = FlynoteDocumentCount.objects.get(flynote=criminal)
        self.assertEqual(count_row.count, 1)

    def test_refresh_for_all_flynotes_updates_multiple_hierarchies(self):
        """refresh_for_all_flynotes() correctly updates counts across multiple roots."""
        judgment1 = Judgment.objects.create(
            case_name="Case 1",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
            flynote_raw="Criminal law \u2014 sentencing; Administrative law \u2014 judicial review",
        )
        judgment2 = Judgment.objects.create(
            case_name="Case 2",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 2, 1),
            language=Language.objects.first(),
            flynote_raw="Criminal law \u2014 admissibility",
        )
        self.updater.update_for_judgment(judgment1)
        self.updater.update_for_judgment(judgment2)
        FlynoteDocumentCount.refresh_for_all_flynotes()

        criminal = Flynote.objects.get(name="Criminal law")
        admin = Flynote.objects.get(name="Administrative law")
        self.assertEqual(FlynoteDocumentCount.objects.get(flynote=criminal).count, 2)
        self.assertEqual(FlynoteDocumentCount.objects.get(flynote=admin).count, 1)

    def test_refresh_for_flynote_requires_root(self):
        with self.assertRaises(ValueError):
            FlynoteDocumentCount.refresh_for_flynote(None)

    def test_refresh_prunes_empty_subtree_leaf_first(self):
        judgment = Judgment.objects.create(
            case_name="Prune Test",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
            flynote_raw="Criminal law — admissibility — trial within a trial",
        )
        self.updater.update_for_judgment(judgment)

        criminal = Flynote.objects.get(name="Criminal law")
        self.assertTrue(Flynote.objects.filter(path__startswith=criminal.path).exists())

        judgment.delete()
        FlynoteDocumentCount.refresh_for_flynote(criminal)

        self.assertFalse(
            Flynote.objects.filter(path__startswith=criminal.path).exists()
        )

    @patch("peachjam.models.flynote.connection.cursor")
    def test_refresh_skips_linked_stale_subtree_and_keeps_pruning(self, mock_cursor):
        class NoopCursor:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute(self, *args, **kwargs):
                return None

        judgment = Judgment.objects.create(
            case_name="Protected prune test",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
            flynote_raw="Criminal law — admissibility — trial within a trial",
        )
        self.updater.update_for_judgment(judgment)

        criminal = Flynote.objects.get(name="Criminal law")
        criminal.add_child(name="Sentencing")
        FlynoteDocumentCount.objects.all().delete()
        mock_cursor.return_value = NoopCursor()

        FlynoteDocumentCount.refresh_for_flynote(criminal)

        self.assertTrue(Flynote.objects.filter(pk=criminal.pk).exists())
        self.assertTrue(Flynote.objects.filter(name="trial within a trial").exists())
        self.assertFalse(Flynote.objects.filter(name="Sentencing").exists())


class FlynoteDeprecationTest(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def make_judgment(self, case_name):
        return Judgment.objects.create(
            case_name=case_name,
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
        )

    @override_settings(
        PEACHJAM={
            **settings.PEACHJAM,
            "SUMMARISE_USE_FLYNOTE_TREE": True,
        }
    )
    @patch("peachjam.tasks.serialise_judgment_flynote_tree")
    @patch("peachjam.tasks.generate_judgment_summary")
    def test_deprecating_parent_cascades_and_queues_directly_linked_judgments(
        self,
        mock_generate_summary,
        mock_serialise_flynote_tree,
    ):
        root = Flynote.add_root(name="Civil procedure")
        child = root.add_child(name="Stay of execution")
        grandchild = child.add_child(name="Urgent applications")

        root_judgment = self.make_judgment("Root flynote judgment")
        child_judgment = self.make_judgment("Child flynote judgment")
        grandchild_judgment = self.make_judgment("Grandchild flynote judgment")
        JudgmentFlynote.objects.create(document=root_judgment, flynote=root)
        JudgmentFlynote.objects.create(document=child_judgment, flynote=child)
        JudgmentFlynote.objects.create(document=grandchild_judgment, flynote=grandchild)

        # Reload the branch before editing it. In production this toggle
        # happens on persisted nodes loaded from the database, and the
        # re-serialisation hook should only run for real name/path changes.
        root = Flynote.objects.get(pk=root.pk)
        child = Flynote.objects.get(pk=child.pk)
        grandchild = Flynote.objects.get(pk=grandchild.pk)
        mock_serialise_flynote_tree.reset_mock()

        root.deprecated = True
        root.save()

        root.refresh_from_db()
        child.refresh_from_db()
        grandchild.refresh_from_db()

        self.assertTrue(root.deprecated)
        self.assertTrue(child.deprecated)
        self.assertTrue(grandchild.deprecated)
        self.assertCountEqual(
            [args.args[0] for args in mock_generate_summary.call_args_list],
            [root_judgment.pk, child_judgment.pk, grandchild_judgment.pk],
        )
        mock_serialise_flynote_tree.assert_not_called()

    @override_settings(
        PEACHJAM={
            **settings.PEACHJAM,
            "SUMMARISE_USE_FLYNOTE_TREE": True,
        }
    )
    @patch("peachjam.tasks.generate_judgment_summary")
    def test_reactivating_parent_cascades_without_queueing_resummaries(
        self,
        mock_generate_summary,
    ):
        root = Flynote.add_root(
            name="Civil procedure",
            deprecated=True,
        )
        child = root.add_child(
            name="Stay of execution",
            deprecated=True,
        )
        grandchild = child.add_child(
            name="Urgent applications",
            deprecated=True,
        )

        root.deprecated = False
        root.save()

        root.refresh_from_db()
        child.refresh_from_db()
        grandchild.refresh_from_db()

        self.assertFalse(root.deprecated)
        self.assertFalse(child.deprecated)
        self.assertFalse(grandchild.deprecated)
        mock_generate_summary.assert_not_called()

    def test_clean_rejects_reactivating_child_under_deprecated_ancestor(self):
        root = Flynote.add_root(
            name="Civil procedure",
            deprecated=True,
        )
        child = root.add_child(
            name="Stay of execution",
            deprecated=True,
        )

        child.deprecated = False
        with self.assertRaisesMessage(
            ValidationError,
            "A flynote cannot be active when any ancestor is deprecated.",
        ):
            child.full_clean()

    @patch("peachjam.tasks.serialise_judgment_flynote_tree")
    def test_renaming_parent_queues_descendant_linked_judgments_for_reserialisation(
        self,
        mock_serialise_judgment_flynote_tree,
    ):
        root = Flynote.add_root(name="Civil procedure")
        child = root.add_child(name="Stay of execution")
        grandchild = child.add_child(name="Urgent applications")

        root_judgment = self.make_judgment("Root flynote judgment")
        grandchild_judgment = self.make_judgment("Grandchild flynote judgment")
        JudgmentFlynote.objects.create(document=root_judgment, flynote=root)
        JudgmentFlynote.objects.create(document=grandchild_judgment, flynote=grandchild)

        root.name = "Civil practice and procedure"
        root.save()

        self.assertCountEqual(
            [
                args.args[0]
                for args in mock_serialise_judgment_flynote_tree.call_args_list
            ],
            [root_judgment.pk, grandchild_judgment.pk],
        )


class FlynoteMergeTest(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def make_judgment(self, case_name):
        return Judgment.objects.create(
            case_name=case_name,
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
        )

    @patch("peachjam.signals.serialise_judgment_flynote_tree")
    @patch("peachjam.models.flynote.queue_refresh_flynote_document_count")
    def test_merge_moves_direct_judgments_and_reparents_children(
        self, mock_queue_refresh, mock_serialise_judgment_flynote_tree
    ):
        root = Flynote.add_root(name="Civil procedure")
        target = root.add_child(name="Stay of execution")
        source = root.add_child(name="Stays of execution")
        source_child = source.add_child(name="Urgent applications")

        direct_judgment = self.make_judgment("Direct source judgment")
        descendant_judgment = self.make_judgment("Descendant source judgment")
        JudgmentFlynote.objects.create(document=direct_judgment, flynote=source)
        JudgmentFlynote.objects.create(
            document=descendant_judgment, flynote=source_child
        )
        mock_serialise_judgment_flynote_tree.reset_mock()

        target.merge_sources_into([source])

        self.assertTrue(
            JudgmentFlynote.objects.filter(
                document=direct_judgment,
                flynote=target,
            ).exists()
        )
        self.assertFalse(Flynote.objects.filter(pk=source.pk).exists())

        source_child.refresh_from_db()
        self.assertEqual(source_child.get_parent().pk, target.pk)
        self.assertTrue(
            JudgmentFlynote.objects.filter(
                document=descendant_judgment,
                flynote=source_child,
            ).exists()
        )
        mock_serialise_judgment_flynote_tree.assert_called_once_with(direct_judgment.pk)
        mock_queue_refresh.assert_called_once_with(root.pk)

    def test_merge_rejects_duplicate_child_names_under_target(self):
        root = Flynote.add_root(name="Civil procedure")
        target = root.add_child(name="Stay of execution")
        source = root.add_child(name="Stays of execution")
        target.add_child(name="Urgent applications")
        source.add_child(name="Urgent applications")

        with self.assertRaisesMessage(
            ValidationError,
            "Cannot merge because the target already has children with these names: Urgent applications.",
        ):
            target.merge_sources_into([source])


class FlynoteListViewTest(TestCase):
    fixtures = [
        "tests/countries",
        "tests/courts",
        "tests/languages",
        "documents/sample_documents",
    ]

    def setUp(self):
        self.updater = FlynoteUpdater()

    def test_renders_topic_list_page(self):
        judgment = Judgment.objects.create(
            case_name="View Test",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
            flynote_raw="Administrative law \u2014 judicial review",
        )
        self.updater.update_for_judgment(judgment)

        response = self.client.get(reverse("flynote_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "peachjam/flynote/list.html")
        self.assertIn("flynotes", response.context)

    def test_uses_precalculated_counts(self):
        judgment = Judgment.objects.create(
            case_name="View Count Test",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
            flynote_raw="Administrative law \u2014 judicial review",
        )
        self.updater.update_for_judgment(judgment)
        admin_flynote = Flynote.objects.get(name="Administrative law")
        FlynoteDocumentCount.refresh_for_flynote(admin_flynote)

        response = self.client.get(reverse("flynote_list"))
        self.assertEqual(response.status_code, 200)
        popular = response.context["flynotes"]
        admin_item = next(
            (p for p in popular if p["flynote"].name == "Administrative law"), None
        )
        self.assertIsNotNone(admin_item)
        self.assertEqual(admin_item["count"], 1)

    def test_redirects_to_judgment_list_when_no_flynotes(self):
        response = self.client.get(reverse("flynote_list"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("judgment_list"))


class JudgmentListFlynoteTopicsTest(TestCase):
    fixtures = [
        "tests/countries",
        "tests/courts",
        "tests/languages",
        "documents/sample_documents",
    ]

    def test_judgment_list_loads(self):
        response = self.client.get(reverse("judgment_list"))
        self.assertEqual(response.status_code, 200)


class UpdateFlynoteTaxonomiesCommandTest(TestCase):
    """Tests for the update_flynote_taxonomies management command flags."""

    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        country = Country.objects.first()
        court = Court.objects.first()
        lang = Language.objects.first()

        self.j1 = Judgment.objects.create(
            case_name="Case A",
            jurisdiction=country,
            court=court,
            date=datetime.date(2025, 1, 1),
            language=lang,
            flynote_raw="Criminal law \u2014 admissibility",
        )
        self.j2 = Judgment.objects.create(
            case_name="Case B",
            jurisdiction=country,
            court=court,
            date=datetime.date(2025, 2, 1),
            language=lang,
            flynote_raw="Contract law \u2014 breach of contract",
        )
        self.j3 = Judgment.objects.create(
            case_name="Case C",
            jurisdiction=country,
            court=court,
            date=datetime.date(2025, 3, 1),
            language=lang,
            flynote_raw="Employment law \u2014 unfair dismissal",
        )

    def test_skip_counts_flag(self):
        """--skip-counts should prevent flynote count refresh."""
        out = StringIO()
        call_command(
            "update_flynote_taxonomies", skip_counts=True, stdout=out, stderr=StringIO()
        )
        output = out.getvalue()

        self.assertIn("Skipping flynote count updates", output)
        self.assertNotIn("Flynote counts refreshed", output)
        self.assertEqual(FlynoteDocumentCount.objects.count(), 0)

    def test_default_refreshes_counts(self):
        """Without --skip-counts, flynote counts should be refreshed."""
        out = StringIO()
        call_command("update_flynote_taxonomies", stdout=out, stderr=StringIO())
        output = out.getvalue()

        self.assertIn("Flynote counts refreshed", output)
        self.assertGreater(FlynoteDocumentCount.objects.count(), 0)

    def test_start_id_filters_judgments(self):
        """--start-id should only process judgments with pk <= start_id."""
        out = StringIO()
        call_command(
            "update_flynote_taxonomies",
            start_id=self.j2.pk,
            skip_counts=True,
            stdout=out,
            stderr=StringIO(),
        )
        output = out.getvalue()

        self.assertIn(f"Starting from judgment pk={self.j2.pk}", output)
        self.assertFalse(
            JudgmentFlynote.objects.filter(document=self.j3).exists(),
            "Judgment with pk > start_id should not be processed",
        )
        self.assertTrue(JudgmentFlynote.objects.filter(document=self.j1).exists())
        self.assertTrue(JudgmentFlynote.objects.filter(document=self.j2).exists())

    def test_start_id_with_limit(self):
        """--start-id combined with --limit should cap the number processed."""
        out = StringIO()
        call_command(
            "update_flynote_taxonomies",
            start_id=self.j3.pk,
            limit=1,
            skip_counts=True,
            stdout=out,
            stderr=StringIO(),
        )
        output = out.getvalue()

        self.assertIn("Processed 1 judgments", output)

    def test_reports_last_pk_processed(self):
        """Output should include the last pk so users know where to resume."""
        out = StringIO()
        call_command(
            "update_flynote_taxonomies",
            skip_counts=True,
            stdout=out,
            stderr=StringIO(),
        )
        output = out.getvalue()

        self.assertIn("Last pk processed:", output)
