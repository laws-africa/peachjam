from django.test import TestCase
from languages_plus.models import Language

from peachjam.models import Legislation


class TestPreferredLanguage(TestCase):
    fixtures = ["tests/countries", "documents/sample_documents", "tests/languages"]
    maxDiff = None

    def test_preferred_language(self):
        response = self.client.get("/legal_instruments/")
        assert response.context.get("documents").count() == 2

    def test_update_work_languages(self):
        doc = Legislation.objects.get(
            expression_frbr_uri="/akn/aa-au/act/1969/civil-aviation-commission/eng@1969-01-17"
        )
        work = doc.work
        work.update_languages()
        self.assertEqual(["eng"], work.languages)

        # create a french copy
        doc2 = Legislation.objects.create(
            jurisdiction=doc.jurisdiction,
            locality=doc.locality,
            frbr_uri_doctype="act",
            frbr_uri_date=doc.frbr_uri_date,
            frbr_uri_number=doc.frbr_uri_number,
            title=doc.title,
            date=doc.date,
            language=Language.objects.get(pk="fr"),
            metadata_json={},
        )
        self.assertNotEqual(doc.pk, doc2.pk)

        work.refresh_from_db()
        self.assertEqual(["eng", "fra"], sorted(work.languages))

        doc2.delete()
        work.refresh_from_db()
        self.assertEqual(["eng"], sorted(work.languages))
