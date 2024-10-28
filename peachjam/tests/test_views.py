from django.test import TestCase

from peachjam.models import PeachJamSettings


class PeachjamViewsTest(TestCase):
    fixtures = ["tests/countries", "documents/sample_documents"]

    def test_login_page(self):
        response = self.client.get("/accounts/login/")
        self.assertTemplateUsed(response, "account/login.html")

    def test_homepage(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        # documents
        self.assertEqual(10, response.context.get("documents_count"))

        recent_judgments = [
            r_j.title for r_j in response.context.get("recent_judgments")
        ]
        self.assertIn(
            "Obi vs Federal Republic of Nigeria [2016] ECOWASCJ 52 (09 November 2016)",
            recent_judgments,
        )

        recent_documents = [
            r_d.title for r_d in response.context.get("recent_documents")
        ]
        self.assertIn(
            "Activity Report of the Pan-African Parliament, July 2016 to June 2017",
            recent_documents,
        )

    def test_judgment_listing(self):
        response = self.client.get("/judgments/")
        self.assertEqual(response.status_code, 200)

        documents = [doc.title for doc in response.context.get("documents")]
        court_classes = [
            court_class.name for court_class in response.context.get("court_classes")
        ]

        self.assertIn(
            "Ababacar and Ors vs Senegal [2018] ECOWASCJ 17 (29 June 2018)",
            documents,
        )
        self.assertIn("High Court", court_classes)

    def test_court_listing(self):
        response = self.client.get("/judgments/ECOWASCJ/")
        self.assertEqual(response.status_code, 200)

        documents = [doc.title for doc in response.context.get("documents")]
        self.assertIn(
            "Ababacar and Ors vs Senegal [2018] ECOWASCJ 17 (29 June 2018)",
            documents,
        )
        self.assertContains(response, "/judgments/ECOWASCJ/2018/")
        self.assertContains(response, "/judgments/ECOWASCJ/2016/")
        self.assertNotIn("years", response.context["facet_data"], [2016, 2018])

    def test_court_year_listing(self):
        response = self.client.get("/judgments/ECOWASCJ/2016/")
        self.assertEqual(response.status_code, 200)

        documents = [doc.title for doc in response.context.get("documents")]

        self.assertIn(
            "Obi vs Federal Republic of Nigeria [2016] ECOWASCJ 52 (09 November 2016)",
            documents,
        )
        self.assertNotIn(
            "Ababacar and Ors vs Senegal [2018] ECOWASCJ 17 (29 June 2018)",
            documents,
        )
        self.assertEqual(response.context["year"], 2016)
        self.assertContains(response, "/judgments/ECOWASCJ/2018/")
        self.assertContains(response, "/judgments/ECOWASCJ/2016/")
        self.assertNotIn("years", response.context["facet_data"], [2016, 2018])

    def test_court_year_listing_bad_year(self):
        self.assertEqual(self.client.get("/judgments/ECOWASCJ/0/").status_code, 404)
        self.assertEqual(
            self.client.get("/judgments/ECOWASCJ/999999/").status_code, 404
        )

    def test_judgment_detail(self):
        response = self.client.get(
            "/akn/aa-au/judgment/ecowascj/2018/17/eng@2018-06-29"
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context["document"].doc_type, "judgment")
        self.assertEqual(
            response.context["document"].expression_frbr_uri,
            "/akn/aa-au/judgment/ecowascj/2018/17/eng@2018-06-29",
        )
        self.assertTrue(hasattr(response.context["document"], "court"))

    def test_legislation_listing(self):
        response = self.client.get("/legislation/")
        self.assertEqual(response.status_code, 200)

        documents = [doc.title for doc in response.context.get("documents")]
        self.assertIn(
            "African Civil Aviation Commission Constitution (AFCAC)",
            documents,
        )
        self.assertEqual(
            [("1969", 1969), ("2005", 2005), ("2010", 2010), ("2020", 2020)],
            sorted(response.context["facet_data"]["years"]["options"]),
        )

    def test_legislation_detail(self):
        response = self.client.get(
            "/akn/aa-au/act/pact/2005/non-aggression-and-common-defence/eng@2005-01-31"
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context["document"].doc_type, "legislation")
        self.assertEqual(
            response.context["document"].expression_frbr_uri,
            "/akn/aa-au/act/pact/2005/non-aggression-and-common-defence/eng@2005-01-31",
        )
        self.assertTrue(hasattr(response.context["document"], "repealed"))

    def test_generic_document_listing(self):
        response = self.client.get("/doc/")
        self.assertEqual(response.status_code, 200)

        documents = [doc.title for doc in response.context.get("documents")]
        self.assertIn(
            "Activity Report of the Pan-African Parliament, July 2016 to June 2017",
            documents,
        )
        self.assertEqual(
            [("2017", 2017)],
            response.context["facet_data"]["years"]["options"],
        )

    def test_generic_document_detail(self):
        response = self.client.get(
            "/akn/aa-au/doc/activity-report/2017/nn/eng@2017-07-03"
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context["document"].doc_type, "generic_document")
        self.assertEqual(
            response.context["document"].expression_frbr_uri,
            "/akn/aa-au/doc/activity-report/2017/nn/eng@2017-07-03",
        )
        self.assertTrue(hasattr(response.context["document"], "authors"))

    def test_robots_txt(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User-agent")

        settings = PeachJamSettings.load()
        settings.robots_txt = None
        settings.save()

        response = self.client.get("/robots.txt")
        self.assertContains(response, "User-agent")
        self.assertNotContains(response, "None")

        settings.robots_txt = "foo\nbar"
        settings.save()

        response = self.client.get("/robots.txt")
        self.assertContains(response, "foo\nbar")
