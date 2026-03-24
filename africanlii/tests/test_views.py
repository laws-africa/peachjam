from django.test import TestCase, override_settings
from django.urls.base import reverse

from africanlii.views.taxonomy import is_doc_index_topic
from peachjam.models import Taxonomy


class AfricanliiViewsTest(TestCase):
    fixtures = ["tests/countries", "documents/sample_documents"]

    def test_homepage(self):
        response = self.client.get(reverse("home_page"))
        self.assertEqual(response.status_code, 200)

        # documents
        self.assertEqual(10, response.context.get("documents_count"))

        court_classes = [
            court_class.name for court_class in response.context.get("court_classes")
        ]
        self.assertIn("High Court", court_classes)

        recent_judgments = [
            r_j.title for r_j in response.context.get("recent_judgments")
        ]
        self.assertIn(
            "Obi vs Federal Republic of Nigeria [2016] ECOWASCJ 52 (09 November 2016)",
            recent_judgments,
        )

        recent_legislation = [
            r_l.title for r_l in response.context.get("recent_legislation")
        ]
        self.assertIn("Divorce Act, 1979", recent_legislation)

        recent_articles = [r_a.title for r_a in response.context.get("recent_articles")]
        self.assertEqual(0, len(recent_articles))

        # should not set csrf token
        self.assertNotContains(response, "csrfmiddlewaretoken")
        # should not set a cookie
        self.assertNotIn("Set-Cookie", response.headers)

    def test_legal_instrument_listing(self):
        response = self.client.get(reverse("agp_legal_instrument_list"))
        self.assertEqual(response.status_code, 301)

    @override_settings(FEDERATED_DOC_INDEX_ROOTS=["case-indexes"])
    def test_is_doc_index_topic_uses_hierarchical_slug(self):
        indexes = Taxonomy.add_root(name="Case Indexes", slug="case-indexes")
        child = indexes.add_child(name="Environment")
        other_root = Taxonomy.add_root(name="Collections", slug="collections")

        self.assertTrue(is_doc_index_topic(indexes))
        self.assertTrue(is_doc_index_topic(child))
        self.assertFalse(is_doc_index_topic(other_root))

    @override_settings(FEDERATED_DOC_INDEX_ROOTS=["case-indexes"])
    def test_taxonomy_detail_redirects_doc_index_topics_to_indexes_url(self):
        indexes = Taxonomy.add_root(name="Case Indexes", slug="case-indexes")
        child = indexes.add_child(name="Environment")

        response = self.client.get(
            reverse(
                "taxonomy_detail",
                kwargs={"topic": indexes.slug, "child": child.slug},
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "doc_index_detail",
                kwargs={"topic": indexes.slug, "child": child.slug},
            ),
            fetch_redirect_response=False,
        )

    @override_settings(FEDERATED_DOC_INDEX_ROOTS=["case-indexes"])
    def test_doc_index_detail_redirects_non_index_topics_back_to_taxonomy_url(self):
        non_index_root = Taxonomy.add_root(name="Collections")
        child = non_index_root.add_child(name="Environment")

        response = self.client.get(
            reverse(
                "doc_index_detail",
                kwargs={"topic": non_index_root.slug, "child": child.slug},
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "taxonomy_detail",
                kwargs={"topic": non_index_root.slug, "child": child.slug},
            ),
            fetch_redirect_response=False,
        )
