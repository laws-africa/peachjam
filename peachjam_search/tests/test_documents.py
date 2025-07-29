from django.test import TestCase  # noqa

from peachjam.models import CoreDocument, Judgment
from peachjam_search.documents import SearchableDocument


class SearchableDocumentTestCase(TestCase):
    fixtures = ["tests/countries", "documents/sample_documents"]

    def test_translated_field(self):
        doc = CoreDocument.objects.filter(nature__code="activity-report").first()
        sd = SearchableDocument()

        self.assertEqual("Activity report", sd.prepare_nature_en(doc))
        doc.nature.name_fr = "Rapport d'activité"
        self.assertEqual("Rapport d'activité", sd.prepare_nature_fr(doc))

    def test_summary_field(self):
        sd = SearchableDocument()
        j = Judgment()
        self.assertEqual("", sd.prepare_summary(j))

        j = Judgment(
            flynote="flynote",
            blurb="blurb",
            case_summary="dodgy <p>summary <b>field</b> fun</p>",
            issues=["issue 1", "issue 2", "issue 3"],
            held=["held 1", "held 2"],
            order="order",
        )

        self.assertEqual(
            "dodgy  summary  field  fun issue 1 issue 2 issue 3 held 1 held 2 order",
            sd.prepare_summary(j),
        )
