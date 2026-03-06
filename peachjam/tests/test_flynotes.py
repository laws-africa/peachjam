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

    def test_trailing_period_stripped(self):
        text = "Employment law \u2013 Severance pay."
        paths = self.parser.parse(text)
        self.assertEqual(paths[0][-1], "Severance pay")


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

    def test_refresh_with_none_root_updates_all(self):
        """refresh_for_flynote(None) updates counts for all flynotes in one go."""
        FlynoteDocumentCount.refresh_for_flynote(None)
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
        FlynoteDocumentCount.refresh_for_flynote(None)
        criminal = Flynote.objects.get(name="Criminal law")
        count_row = FlynoteDocumentCount.objects.get(flynote=criminal)
        self.assertEqual(count_row.count, 1)

    def test_refresh_with_none_root_updates_multiple_hierarchies(self):
        """refresh_for_flynote(None) correctly updates counts across multiple roots."""
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
        FlynoteDocumentCount.refresh_for_flynote(None)

        criminal = Flynote.objects.get(name="Criminal law")
        admin = Flynote.objects.get(name="Administrative law")
        self.assertEqual(FlynoteDocumentCount.objects.get(flynote=criminal).count, 2)
        self.assertEqual(FlynoteDocumentCount.objects.get(flynote=admin).count, 1)


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
        self.assertNotIn("Refreshing flynote document counts", output)
        self.assertEqual(FlynoteDocumentCount.objects.count(), 0)

    def test_default_refreshes_counts(self):
        """Without --skip-counts, flynote counts should be refreshed."""
        out = StringIO()
        call_command("update_flynote_taxonomies", stdout=out, stderr=StringIO())
        output = out.getvalue()

        self.assertIn("Refreshing flynote document counts", output)
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
