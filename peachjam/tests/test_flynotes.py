import datetime
from io import StringIO

from countries_plus.models import Country
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from languages_plus.models import Language

from peachjam.analysis.flynotes import FlynoteParser, FlynoteUpdater
from peachjam.models import Court, Judgment
from peachjam.models.flynote import Flynote, FlynoteDocumentCount, JudgmentFlynote


class ParseFlynoteTextTest(TestCase):
    def setUp(self):
        self.parser = FlynoteParser()

    def test_empty_input(self):
        self.assertEqual(self.parser.parse(""), [])
        self.assertEqual(self.parser.parse(None), [])

    def test_prose_flynote_skipped(self):
        text = "Contract between a lender and a borrower purporting to be a contract of sale."
        self.assertEqual(self.parser.parse(text), [])

    def test_html_prose_flynote_skipped(self):
        text = '<p><span style="color:#000000">Contract between a lender and borrower.</span></p>'
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

    def test_html_tags_stripped(self):
        text = "<p>Employment law \u2013 Severance pay \u2013 Jurisdiction</p>"
        paths = self.parser.parse(text)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0], ["Employment law", "Severance pay", "Jurisdiction"])

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

    def test_html_block_tags_preserve_multiline_flynotes(self):
        text = (
            "<p>Criminal law \u2014 admissibility \u2014 trial within a trial</p>"
            "<p>Administrative law \u2014 judicial review</p>"
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


class GetOrCreateFlynoteNodeTest(TestCase):
    def setUp(self):
        self.updater = FlynoteUpdater()

    def test_creates_new_top_level(self):
        node = self.updater.get_or_create_node(None, "Criminal law")
        self.assertIsNotNone(node)
        self.assertEqual(node.name, "Criminal law")
        self.assertEqual(node.slug, "criminal-law")
        self.assertTrue(node.is_root())

    def test_returns_existing_by_slug(self):
        Flynote.add_root(name="Criminal law", slug="criminal-law")
        found = self.updater.get_or_create_node(None, "Criminal law")
        self.assertEqual(Flynote.objects.filter(slug="criminal-law").count(), 1)
        self.assertEqual(found.name, "Criminal law")

    def test_returns_existing_by_normalised_name(self):
        Flynote.add_root(name="Criminal Law", slug="criminal-law")
        found = self.updater.get_or_create_node(None, "criminal law")
        self.assertEqual(found.name, "Criminal Law")

    def test_creates_nested_nodes(self):
        parent = self.updater.get_or_create_node(None, "Criminal law")
        child = self.updater.get_or_create_node(parent, "admissibility")
        self.assertIsNotNone(child)
        self.assertEqual(child.slug, "criminal-law-admissibility")
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
            flynote=(
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

        self.judgment.flynote = "Contract law \u2014 breach of contract"
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
            flynote="Criminal law \u2014 sentencing",
        )
        self.updater.update_for_judgment(judgment2)

        self.assertEqual(Flynote.objects.filter(name="Criminal law").count(), 1)
        self.assertEqual(Flynote.objects.get(name="Criminal law").pk, criminal_pk)

    def test_empty_flynote_skips(self):
        self.judgment.flynote = ""
        self.judgment.save()

        self.updater.update_for_judgment(self.judgment)
        self.assertEqual(
            JudgmentFlynote.objects.filter(document=self.judgment).count(), 0
        )

    def test_prose_flynote_skips(self):
        self.judgment.flynote = "This is a plain prose description of the case."
        self.judgment.save()

        self.updater.update_for_judgment(self.judgment)
        self.assertEqual(
            JudgmentFlynote.objects.filter(document=self.judgment).count(), 0
        )

    def test_multiline_flynotes_link_separate_leaf_nodes(self):
        self.judgment.flynote = (
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
            flynote="Criminal law \u2014 admissibility",
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
            flynote="Criminal law \u2014 admissibility \u2014 trial within a trial",
        )
        judgment2 = Judgment.objects.create(
            case_name="Case 2",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 2, 1),
            language=Language.objects.first(),
            flynote="Criminal law \u2014 sentencing",
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
            flynote="Criminal law \u2014 admissibility",
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
            flynote="Criminal law \u2014 sentencing; Administrative law \u2014 judicial review",
        )
        judgment2 = Judgment.objects.create(
            case_name="Case 2",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 2, 1),
            language=Language.objects.first(),
            flynote="Criminal law \u2014 admissibility",
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


class FlynoteTopicListViewTest(TestCase):
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
            flynote="Administrative law \u2014 judicial review",
        )
        self.updater.update_for_judgment(judgment)

        response = self.client.get(reverse("flynote_topic_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "peachjam/flynote/list.html")
        self.assertIn("all_topics", response.context)

    def test_uses_precalculated_counts(self):
        judgment = Judgment.objects.create(
            case_name="View Count Test",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
            flynote="Administrative law \u2014 judicial review",
        )
        self.updater.update_for_judgment(judgment)
        admin_flynote = Flynote.objects.get(name="Administrative law")
        FlynoteDocumentCount.refresh_for_flynote(admin_flynote)

        response = self.client.get(reverse("flynote_topic_list"))
        self.assertEqual(response.status_code, 200)
        popular = response.context["popular_topics"]
        admin_item = next(
            (p for p in popular if p["topic"].name == "Administrative law"), None
        )
        self.assertIsNotNone(admin_item)
        self.assertEqual(admin_item["count"], 1)

    def test_redirects_to_judgment_list_when_no_flynotes(self):
        response = self.client.get(reverse("flynote_topic_list"))
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
            flynote="Criminal law \u2014 admissibility",
        )
        self.j2 = Judgment.objects.create(
            case_name="Case B",
            jurisdiction=country,
            court=court,
            date=datetime.date(2025, 2, 1),
            language=lang,
            flynote="Contract law \u2014 breach of contract",
        )
        self.j3 = Judgment.objects.create(
            case_name="Case C",
            jurisdiction=country,
            court=court,
            date=datetime.date(2025, 3, 1),
            language=lang,
            flynote="Employment law \u2014 unfair dismissal",
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
