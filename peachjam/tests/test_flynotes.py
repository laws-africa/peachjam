import datetime

from countries_plus.models import Country
from django.test import TestCase
from django.urls import reverse
from languages_plus.models import Language

from peachjam.flynotes import (
    get_or_create_taxonomy_node,
    normalise_flynote_name,
    parse_flynote_text,
    update_flynote_taxonomy_for_judgment,
)
from peachjam.models import Court, Judgment, PeachJamSettings
from peachjam.models.taxonomies import DocumentTopic, Taxonomy


class ParseFlynoteTextTest(TestCase):
    def test_empty_input(self):
        self.assertEqual(parse_flynote_text(""), [])
        self.assertEqual(parse_flynote_text(None), [])

    def test_prose_flynote_skipped(self):
        text = "Contract between a lender and a borrower purporting to be a contract of sale."
        self.assertEqual(parse_flynote_text(text), [])

    def test_html_prose_flynote_skipped(self):
        text = '<p><span style="color:#000000">Contract between a lender and borrower.</span></p>'
        self.assertEqual(parse_flynote_text(text), [])

    def test_simple_chain_with_em_dashes(self):
        text = "Criminal law \u2014 admissibility \u2014 trial within a trial"
        paths = parse_flynote_text(text)
        self.assertEqual(len(paths), 1)
        self.assertEqual(
            paths[0], ["Criminal law", "admissibility", "trial within a trial"]
        )

    def test_simple_chain_with_en_dashes(self):
        text = "Employment law \u2013 Severance pay \u2013 Jurisdiction"
        paths = parse_flynote_text(text)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0], ["Employment law", "Severance pay", "Jurisdiction"])

    def test_simple_chain_with_hyphens(self):
        text = "Administrative law - retrospective application - discrimination"
        paths = parse_flynote_text(text)
        self.assertEqual(len(paths), 1)
        self.assertEqual(
            paths[0],
            ["Administrative law", "retrospective application", "discrimination"],
        )

    def test_semicolons_create_sibling_branches(self):
        text = "Criminal law \u2014 admissibility \u2014 trial within a trial; right to legal representation"
        paths = parse_flynote_text(text)
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
        paths = parse_flynote_text(text)
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
        paths = parse_flynote_text(text)
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
        paths = parse_flynote_text(text)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0], ["Employment law", "Severance pay", "Jurisdiction"])

    def test_trailing_period_stripped(self):
        text = "Employment law \u2013 Severance pay."
        paths = parse_flynote_text(text)
        self.assertEqual(paths[0][-1], "Severance pay")


class NormaliseFlynoteNameTest(TestCase):
    def test_basic_normalisation(self):
        self.assertEqual(normalise_flynote_name("Criminal Law"), "criminal-law")

    def test_strips_whitespace(self):
        self.assertEqual(normalise_flynote_name("  Criminal Law  "), "criminal-law")

    def test_consistent_slugs(self):
        self.assertEqual(
            normalise_flynote_name("Right to fair hearing"),
            normalise_flynote_name("right to fair hearing"),
        )


class GetOrCreateTaxonomyNodeTest(TestCase):
    def setUp(self):
        self.root = Taxonomy.add_root(name="Flynotes")

    def test_creates_new_child(self):
        node = get_or_create_taxonomy_node(self.root, "Criminal law")
        self.assertEqual(node.name, "Criminal law")
        self.assertEqual(node.get_parent().pk, self.root.pk)

    def test_returns_existing_child_by_slug(self):
        original = self.root.add_child(name="Criminal law")
        found = get_or_create_taxonomy_node(self.root, "Criminal law")
        self.assertEqual(found.pk, original.pk)

    def test_returns_existing_child_by_normalised_name(self):
        original = self.root.add_child(name="Criminal Law")
        found = get_or_create_taxonomy_node(self.root, "criminal law")
        self.assertEqual(found.pk, original.pk)

    def test_creates_nested_nodes(self):
        parent = get_or_create_taxonomy_node(self.root, "Criminal law")
        child = get_or_create_taxonomy_node(parent, "admissibility")
        self.assertEqual(child.get_parent().pk, parent.pk)


class UpdateFlynoteTaxonomyForJudgmentTest(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.root = Taxonomy.add_root(name="Case Law Flynotes")
        settings = PeachJamSettings.load()
        settings.flynote_taxonomy_root = self.root
        settings.save()

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
        update_flynote_taxonomy_for_judgment(self.judgment.pk)

        self.assertTrue(Taxonomy.objects.filter(name="Criminal law").exists())
        self.assertTrue(Taxonomy.objects.filter(name="admissibility").exists())
        self.assertTrue(Taxonomy.objects.filter(name="trial within a trial").exists())
        self.assertTrue(
            Taxonomy.objects.filter(name="circumstantial evidence").exists()
        )
        self.assertTrue(Taxonomy.objects.filter(name="Blom principles").exists())

    def test_links_judgment_to_leaf_nodes_only(self):
        update_flynote_taxonomy_for_judgment(self.judgment.pk)

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
        update_flynote_taxonomy_for_judgment(self.judgment.pk)

        criminal = Taxonomy.objects.get(name="Criminal law")
        self.assertEqual(criminal.get_parent().pk, self.root.pk)

        admissibility = Taxonomy.objects.get(name="admissibility")
        self.assertEqual(admissibility.get_parent().pk, criminal.pk)

        trial = Taxonomy.objects.get(name="trial within a trial")
        self.assertEqual(trial.get_parent().pk, admissibility.pk)

        circumstantial = Taxonomy.objects.get(name="circumstantial evidence")
        self.assertEqual(circumstantial.get_parent().pk, criminal.pk)

    def test_clears_old_links_on_reprocess(self):
        update_flynote_taxonomy_for_judgment(self.judgment.pk)
        initial_count = DocumentTopic.objects.filter(document=self.judgment).count()
        self.assertEqual(initial_count, 2)

        self.judgment.flynote = "Contract law \u2014 breach of contract"
        self.judgment.save()
        update_flynote_taxonomy_for_judgment(self.judgment.pk)

        linked_topics = set(
            DocumentTopic.objects.filter(document=self.judgment).values_list(
                "topic__name", flat=True
            )
        )
        self.assertEqual(linked_topics, {"breach of contract"})

    def test_reuses_existing_taxonomy_nodes(self):
        update_flynote_taxonomy_for_judgment(self.judgment.pk)
        criminal_pk = Taxonomy.objects.get(name="Criminal law").pk

        judgment2 = Judgment.objects.create(
            case_name="Test Case 2",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 2, 1),
            language=Language.objects.first(),
            flynote="Criminal law \u2014 sentencing",
        )
        update_flynote_taxonomy_for_judgment(judgment2.pk)

        self.assertEqual(Taxonomy.objects.filter(name="Criminal law").count(), 1)
        self.assertEqual(Taxonomy.objects.get(name="Criminal law").pk, criminal_pk)

    def test_no_root_configured_skips(self):
        settings = PeachJamSettings.load()
        settings.flynote_taxonomy_root = None
        settings.save()

        update_flynote_taxonomy_for_judgment(self.judgment.pk)
        self.assertEqual(
            DocumentTopic.objects.filter(document=self.judgment).count(), 0
        )

    def test_empty_flynote_skips(self):
        self.judgment.flynote = ""
        self.judgment.save()

        update_flynote_taxonomy_for_judgment(self.judgment.pk)
        self.assertEqual(
            DocumentTopic.objects.filter(document=self.judgment).count(), 0
        )

    def test_prose_flynote_skips(self):
        self.judgment.flynote = "This is a plain prose description of the case."
        self.judgment.save()

        update_flynote_taxonomy_for_judgment(self.judgment.pk)
        self.assertEqual(
            DocumentTopic.objects.filter(document=self.judgment).count(), 0
        )


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

    def test_redirects_to_taxonomy_page(self):
        response = self.client.get(reverse("flynote_topic_list"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.root.get_absolute_url())

    def test_redirects_to_judgment_list_when_no_root(self):
        settings = PeachJamSettings.load()
        settings.flynote_taxonomy_root = None
        settings.save()

        response = self.client.get(reverse("flynote_topic_list"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("judgment_list"))


class JudgmentDetailFlynoteContextTest(TestCase):
    """Test the flynote context logic on JudgmentDetailView without rendering the full template
    (avoids pre-existing NoReverseMatch for 'document_similar_docs')."""

    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.root = Taxonomy.add_root(name="Case Law Flynotes")
        settings = PeachJamSettings.load()
        settings.flynote_taxonomy_root = self.root
        settings.save()

        self.judgment = Judgment.objects.create(
            case_name="Flynote Detail Test",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
            flynote="Criminal law \u2014 admissibility \u2014 trial within a trial",
            case_summary="Test summary",
        )
        update_flynote_taxonomy_for_judgment(self.judgment.pk)

    def test_add_flynote_taxonomies_builds_paths(self):
        from peachjam.views.judgment import JudgmentDetailView

        view = JudgmentDetailView()
        view.object = self.judgment
        context = {"taxonomies": {}}
        view.add_flynote_taxonomies(context)

        self.assertIn("flynote_taxonomies", context)
        paths = context["flynote_taxonomies"]
        self.assertEqual(len(paths), 1)
        names = [node["name"] for node in paths[0]]
        self.assertEqual(
            names, ["Criminal law", "admissibility", "trial within a trial"]
        )

    def test_flynote_taxonomies_have_urls(self):
        from peachjam.views.judgment import JudgmentDetailView

        view = JudgmentDetailView()
        view.object = self.judgment
        context = {"taxonomies": {}}
        view.add_flynote_taxonomies(context)

        for path in context["flynote_taxonomies"]:
            for node in path:
                self.assertIn("url", node)
                self.assertTrue(node["url"].startswith("/"))

    def test_flynote_topics_excluded_from_regular_taxonomies(self):
        from peachjam.views.judgment import JudgmentDetailView

        view = JudgmentDetailView()
        view.object = self.judgment

        all_topic_ids = set(
            self.judgment.taxonomies.values_list("topic__pk", flat=True)
        )
        context = {
            "taxonomies": Taxonomy.get_tree_for_items(
                Taxonomy.objects.filter(pk__in=all_topic_ids)
            )
        }
        view.add_flynote_taxonomies(context)

        for taxonomy_node in context["taxonomies"]:
            self.assertNotEqual(taxonomy_node.name, "Criminal law")
            self.assertNotEqual(taxonomy_node.name, "admissibility")

    def test_no_flynote_root_returns_no_context(self):
        from peachjam.views.judgment import JudgmentDetailView

        settings = PeachJamSettings.load()
        settings.flynote_taxonomy_root = None
        settings.save()

        view = JudgmentDetailView()
        view.object = self.judgment
        context = {"taxonomies": {}}
        view.add_flynote_taxonomies(context)

        self.assertNotIn("flynote_taxonomies", context)


class JudgmentListFlynoteTopicsTest(TestCase):
    fixtures = [
        "tests/countries",
        "tests/courts",
        "tests/languages",
        "documents/sample_documents",
    ]

    def test_judgment_list_shows_explore_topics_link(self):
        root = Taxonomy.add_root(name="Case Law Flynotes")
        settings = PeachJamSettings.load()
        settings.flynote_taxonomy_root = root
        settings.save()

        response = self.client.get(reverse("judgment_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Explore case law by topic")

    def test_judgment_list_hides_explore_topics_when_no_root(self):
        settings = PeachJamSettings.load()
        settings.flynote_taxonomy_root = None
        settings.save()

        response = self.client.get(reverse("judgment_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Explore case law by topic")
