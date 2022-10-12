from django.test import TestCase


class PeachjamViewsTest(TestCase):
    fixtures = ["documents/sample_documents"]

    def test_login_page(self):
        response = self.client.get("/accounts/login/")
        self.assertTemplateUsed(response, "account/login.html")

    def test_homepage(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        # documents
        self.assertEqual(response.context_data["documents_count"], 8)
        self.assertEqual(len(response.context_data["recent_judgments"]), 2)
        self.assertEqual(len(response.context_data["recent_documents"]), 2)
        self.assertEqual(len(response.context_data["recent_instruments"]), 2)
        self.assertEqual(len(response.context_data["recent_legislation"]), 2)

        # authors
        self.assertEqual(len(response.context_data["authors"]), 1)

    def test_judgment_listing(self):
        response = self.client.get("/judgments/")
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(response.context_data["documents"]), 2)
        self.assertEqual(len(response.context_data["facet_data"]["courts"]), 1)
        self.assertEqual(response.context_data["facet_data"]["years"], [2016, 2018])

    def test_judgment_detail(self):
        response = self.client.get(
            "/akn/aa-au/judgment/ecowascj/2018/17/eng@2018-06-29"
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context_data["document"].doc_type, "judgment")
        self.assertEqual(
            response.context_data["document"].expression_frbr_uri,
            "/akn/aa-au/judgment/ecowascj/2018/17/eng@2018-06-29",
        )
        self.assertTrue(hasattr(response.context_data["document"], "court"))
        self.assertEqual(response.context_data["document"].date.year, 2018)

    def test_legislation_listing(self):
        response = self.client.get("/legislation/")
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(response.context_data["documents"]), 2)
        self.assertEqual(len(response.context_data["facet_data"]["courts"]), 0)
        self.assertEqual(response.context_data["facet_data"]["years"], [1969, 2005])

    def test_legislation_detail(self):
        response = self.client.get(
            "/akn/aa-au/act/pact/2005/non-aggression-and-common-defence/eng@2005-01-31"
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context_data["document"].doc_type, "legislation")
        self.assertEqual(
            response.context_data["document"].expression_frbr_uri,
            "/akn/aa-au/act/pact/2005/non-aggression-and-common-defence/eng@2005-01-31",
        )
        self.assertEqual(response.context_data["document"].date.year, 2005)
        self.assertTrue(hasattr(response.context_data["document"], "repealed"))
        self.assertFalse(hasattr(response.context_data["document"], "author"))

    def test_legal_instrument_listing(self):
        response = self.client.get("/legal_instruments/")
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(response.context_data["documents"]), 2)
        self.assertEqual(len(response.context_data["facet_data"]["authors"]), 0)
        self.assertEqual(len(response.context_data["facet_data"]["courts"]), 0)
        self.assertEqual(response.context_data["facet_data"]["years"], [2007])

    def test_legal_instrument_detail(self):
        response = self.client.get(
            "/akn/aa-au/act/charter/2007/elections-democracy-and-governance/eng@2007-01-30"
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context_data["document"].doc_type, "legal_instrument")
        self.assertEqual(
            response.context_data["document"].expression_frbr_uri,
            "/akn/aa-au/act/charter/2007/elections-democracy-and-governance/eng@2007-01-30",
        )
        self.assertEqual(response.context_data["document"].date.year, 2007)
        self.assertTrue(hasattr(response.context_data["document"], "author"))

    def test_generic_document_listing(self):
        response = self.client.get("/generic_documents/")
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(response.context_data["documents"]), 2)
        self.assertEqual(len(response.context_data["facet_data"]["courts"]), 0)
        self.assertEqual(len(response.context_data["facet_data"]["authors"]), 0)
        self.assertEqual(response.context_data["facet_data"]["years"], [2017])

    def test_generic_document_detail(self):
        response = self.client.get(
            "/akn/aa-au/doc/activity-report/2017/nn/eng@2017-07-03"
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context_data["document"].doc_type, "generic_document")
        self.assertEqual(
            response.context_data["document"].expression_frbr_uri,
            "/akn/aa-au/doc/activity-report/2017/nn/eng@2017-07-03",
        )
        self.assertEqual(response.context_data["document"].date.year, 2017)
        self.assertTrue(hasattr(response.context_data["document"], "author"))
