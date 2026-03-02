import datetime

from countries_plus.models import Country
from django.test import TestCase
from django.urls import reverse
from languages_plus.models import Language

from peachjam.analysis.flynotes import FlynoteParser, FlynoteTaxonomyUpdater
from peachjam.models import Court, Judgment, PeachJamSettings
from peachjam.models.taxonomies import DocumentTopic, Taxonomy, TaxonomyDocumentCount


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


class GetOrCreateTaxonomyNodeTest(TestCase):
    def setUp(self):
        self.root = Taxonomy.add_root(name="Flynotes")
        self.updater = FlynoteTaxonomyUpdater()

    def test_creates_new_child(self):
        node = self.updater.get_or_create_node(self.root, "Criminal law")
        self.assertEqual(node.name, "Criminal law")
        self.assertEqual(node.get_parent().pk, self.root.pk)

    def test_returns_existing_child_by_slug(self):
        original = self.root.add_child(name="Criminal law")
        found = self.updater.get_or_create_node(self.root, "Criminal law")
        self.assertEqual(found.pk, original.pk)

    def test_returns_existing_child_by_normalised_name(self):
        original = self.root.add_child(name="Criminal Law")
        found = self.updater.get_or_create_node(self.root, "criminal law")
        self.assertEqual(found.pk, original.pk)

    def test_creates_nested_nodes(self):
        parent = self.updater.get_or_create_node(self.root, "Criminal law")
        child = self.updater.get_or_create_node(parent, "admissibility")
        self.assertEqual(child.get_parent().pk, parent.pk)


class UpdateFlynoteTaxonomyForJudgmentTest(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.root = Taxonomy.add_root(name="Case Law Flynotes")
        settings = PeachJamSettings.load()
        settings.flynote_taxonomy_root = self.root
        settings.save()

        self.updater = FlynoteTaxonomyUpdater()

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

    def test_creates_taxonomy_nodes(self):
        self.updater.update_for_judgment(self.judgment)

        self.assertTrue(Taxonomy.objects.filter(name="Criminal law").exists())
        self.assertTrue(Taxonomy.objects.filter(name="admissibility").exists())
        self.assertTrue(Taxonomy.objects.filter(name="trial within a trial").exists())
        self.assertTrue(
            Taxonomy.objects.filter(name="circumstantial evidence").exists()
        )
        self.assertTrue(Taxonomy.objects.filter(name="Blom principles").exists())

    def test_links_judgment_to_leaf_nodes_only(self):
        self.updater.update_for_judgment(self.judgment)

        linked_topics = set(
            DocumentTopic.objects.filter(document=self.judgment).values_list(
                "topic__name", flat=True
            )
        )
        self.assertIn("trial within a trial", linked_topics)
        self.assertIn("Blom principles", linked_topics)
        self.assertNotIn("Criminal law", linked_topics)
        self.assertNotIn("admissibility", linked_topics)
        self.assertNotIn("circumstantial evidence", linked_topics)

    def test_taxonomy_tree_structure(self):
        self.updater.update_for_judgment(self.judgment)

        criminal = Taxonomy.objects.get(name="Criminal law")
        self.assertEqual(criminal.get_parent().pk, self.root.pk)

        admissibility = Taxonomy.objects.get(name="admissibility")
        self.assertEqual(admissibility.get_parent().pk, criminal.pk)

        trial = Taxonomy.objects.get(name="trial within a trial")
        self.assertEqual(trial.get_parent().pk, admissibility.pk)

        circumstantial = Taxonomy.objects.get(name="circumstantial evidence")
        self.assertEqual(circumstantial.get_parent().pk, criminal.pk)

    def test_clears_old_links_on_reprocess(self):
        self.updater.update_for_judgment(self.judgment)
        initial_count = DocumentTopic.objects.filter(document=self.judgment).count()
        self.assertEqual(initial_count, 2)

        self.judgment.flynote = "Contract law \u2014 breach of contract"
        self.judgment.save()
        self.updater.update_for_judgment(self.judgment)

        linked_topics = set(
            DocumentTopic.objects.filter(document=self.judgment).values_list(
                "topic__name", flat=True
            )
        )
        self.assertEqual(linked_topics, {"breach of contract"})

    def test_reuses_existing_taxonomy_nodes(self):
        self.updater.update_for_judgment(self.judgment)
        criminal_pk = Taxonomy.objects.get(name="Criminal law").pk

        judgment2 = Judgment.objects.create(
            case_name="Test Case 2",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 2, 1),
            language=Language.objects.first(),
            flynote="Criminal law \u2014 sentencing",
        )
        self.updater.update_for_judgment(judgment2)

        self.assertEqual(Taxonomy.objects.filter(name="Criminal law").count(), 1)
        self.assertEqual(Taxonomy.objects.get(name="Criminal law").pk, criminal_pk)

    def test_no_root_configured_skips(self):
        settings = PeachJamSettings.load()
        settings.flynote_taxonomy_root = None
        settings.save()

        self.updater.update_for_judgment(self.judgment)
        self.assertEqual(
            DocumentTopic.objects.filter(document=self.judgment).count(), 0
        )

    def test_empty_flynote_skips(self):
        self.judgment.flynote = ""
        self.judgment.save()

        self.updater.update_for_judgment(self.judgment)
        self.assertEqual(
            DocumentTopic.objects.filter(document=self.judgment).count(), 0
        )

    def test_prose_flynote_skips(self):
        self.judgment.flynote = "This is a plain prose description of the case."
        self.judgment.save()

        self.updater.update_for_judgment(self.judgment)
        self.assertEqual(
            DocumentTopic.objects.filter(document=self.judgment).count(), 0
        )


class TaxonomyDocumentCountTest(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.root = Taxonomy.add_root(name="Case Law Flynotes")
        settings = PeachJamSettings.load()
        settings.flynote_taxonomy_root = self.root
        settings.save()

        self.updater = FlynoteTaxonomyUpdater()

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
        TaxonomyDocumentCount.refresh_for_taxonomy(self.root)

        criminal = Taxonomy.objects.get(name="Criminal law")
        count_row = TaxonomyDocumentCount.objects.get(taxonomy=criminal)
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
        TaxonomyDocumentCount.refresh_for_taxonomy(self.root)

        criminal = Taxonomy.objects.get(name="Criminal law")
        count_row = TaxonomyDocumentCount.objects.get(taxonomy=criminal)
        self.assertEqual(count_row.count, 2)

    def test_refresh_with_none_root_skips(self):
        TaxonomyDocumentCount.refresh_for_taxonomy(None)
        self.assertEqual(TaxonomyDocumentCount.objects.count(), 0)


class FlynoteTopicListViewTest(TestCase):
    fixtures = [
        "tests/countries",
        "tests/courts",
        "tests/languages",
        "documents/sample_documents",
    ]

    def setUp(self):
        self.root = Taxonomy.add_root(name="Case Law Flynotes")
        settings = PeachJamSettings.load()
        settings.flynote_taxonomy_root = self.root
        settings.save()

    def test_renders_topic_list_page(self):
        response = self.client.get(reverse("flynote_topic_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "peachjam/flynote_topic_list.html")
        self.assertIn("all_topics", response.context)

    def test_uses_precalculated_counts(self):
        updater = FlynoteTaxonomyUpdater()
        judgment = Judgment.objects.create(
            case_name="View Count Test",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
            flynote="Administrative law \u2014 judicial review",
        )
        updater.update_for_judgment(judgment)
        TaxonomyDocumentCount.refresh_for_taxonomy(self.root)

        response = self.client.get(reverse("flynote_topic_list"))
        self.assertEqual(response.status_code, 200)
        popular = response.context["popular_topics"]
        admin_item = next(
            (p for p in popular if p["topic"].name == "Administrative law"), None
        )
        self.assertIsNotNone(admin_item)
        self.assertEqual(admin_item["count"], 1)

    def test_redirects_to_judgment_list_when_no_root(self):
        settings = PeachJamSettings.load()
        settings.flynote_taxonomy_root = None
        settings.save()

        response = self.client.get(reverse("flynote_topic_list"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("judgment_list"))


class JudgmentDetailFlynoteContextTest(TestCase):
    """Test that flynote taxonomy nodes are excluded from the regular taxonomy queryset."""

    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.root = Taxonomy.add_root(name="Case Law Flynotes")
        settings = PeachJamSettings.load()
        settings.flynote_taxonomy_root = self.root
        settings.save()

        self.updater = FlynoteTaxonomyUpdater()

        self.judgment = Judgment.objects.create(
            case_name="Flynote Detail Test",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
            flynote="Criminal law \u2014 admissibility \u2014 trial within a trial",
            case_summary="Test summary",
        )
        self.updater.update_for_judgment(self.judgment)

    def test_flynote_topics_excluded_from_regular_taxonomies(self):
        from peachjam.views.judgment import JudgmentDetailView

        view = JudgmentDetailView()
        view.object = self.judgment

        qs = view.get_taxonomy_queryset()
        tree = Taxonomy.get_tree_for_items(qs)

        for taxonomy_node in tree:
            self.assertNotEqual(taxonomy_node.name, "Criminal law")
            self.assertNotEqual(taxonomy_node.name, "admissibility")
            self.assertNotEqual(taxonomy_node.name, "trial within a trial")


class JudgmentListFlynoteTopicsTest(TestCase):
    fixtures = [
        "tests/countries",
        "tests/courts",
        "tests/languages",
        "documents/sample_documents",
    ]

    def test_judgment_list_loads(self):
        root = Taxonomy.add_root(name="Case Law Flynotes")
        settings = PeachJamSettings.load()
        settings.flynote_taxonomy_root = root
        settings.save()

        response = self.client.get(reverse("judgment_list"))
        self.assertEqual(response.status_code, 200)
