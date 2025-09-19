from django.test import TestCase


class AfricanliiViewsTest(TestCase):
    fixtures = ["tests/countries", "documents/sample_documents"]

    def test_homepage(self):
        response = self.client.get("/")
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

    def test_legal_instrument_listing(self):
        response = self.client.get("/legal-instruments/")
        self.assertEqual(response.status_code, 301)
