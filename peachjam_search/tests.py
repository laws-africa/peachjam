from django.test import TestCase  # noqa

from peachjam.models import CoreDocument
from peachjam_search.documents import SearchableDocument


class SearchableDocumentTestCase(TestCase):
    fixtures = ["tests/countries", "documents/sample_documents"]

    def test_translated_field(self):
        doc = CoreDocument.objects.filter(nature__code="activity-report").first()
        sd = SearchableDocument()

        self.assertEqual("Activity report", sd.prepare_nature_en(doc))
        doc.nature.name_fr = "Rapport d'activité"
        self.assertEqual("Rapport d'activité", sd.prepare_nature_fr(doc))
