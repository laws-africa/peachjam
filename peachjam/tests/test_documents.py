from django.test import TestCase

from peachjam.models import CoreDocument


class CoreDocumentTestCase(TestCase):
    fixtures = ["documents/sample_documents"]

    def test_document_text_from_html(self):
        doc = CoreDocument.objects.get(
            expression_frbr_uri="/akn/aa-au/doc/activity-report/2017/nn/eng@2017-07-03"
        )
        self.assertFalse(hasattr(doc, "document_content"))
        self.assertEqual(
            "Activity Report of the Pan-African Parliament, July 2016 to June 2017",
            doc.get_content_as_text().strip()[:69],
        )
        self.assertTrue(hasattr(doc, "document_content"))
        self.assertEqual(
            "Activity Report of the Pan-African Parliament, July 2016 to June 2017",
            doc.document_content.content_text.strip()[:69],
        )

        # change the source and update
        doc.content_html = "<p>test</p>"
        doc.update_text_content()
        self.assertEqual("test", doc.get_content_as_text())

        doc.refresh_from_db()
        self.assertEqual("test", doc.get_content_as_text())
