from datetime import date

from django.test import RequestFactory, TestCase

from peachjam.models import Country, Language, Legislation
from peachjam.views import DocumentProvisionSimilarView
from peachjam_ml.models import ContentChunk


class DocumentProvisionSimilarViewTest(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def make_document(self, title, number):
        document = Legislation.objects.create(
            jurisdiction=Country.objects.first(),
            date=date(2020, 1, 2),
            language=Language.objects.first(),
            frbr_uri_doctype="act",
            frbr_uri_number=number,
            frbr_uri_date="2020",
            title=title,
            published=True,
        )
        content = document.get_or_create_document_content(True)
        content.content_html_is_akn = True
        content.content_html = """
          <div class="akn-akomaNtoso">
            <section id="sec_1" data-eid="sec_1">
              <span class="akn-num">1.</span>
              <p>Section content</p>
            </section>
          </div>
        """
        content.toc_json = [{"id": "sec_1", "title": "Section 1", "children": []}]
        content.save()
        return document

    def test_get_queryset_attaches_similar_provisions_to_documents(self):
        source = self.make_document("Source", "source")
        target = self.make_document("Target", "target")
        unrelated = self.make_document("Unrelated", "unrelated")
        source_embedding = [1.0] + [0.0] * 1023

        ContentChunk.objects.create(
            document=source,
            type="provision",
            text="source",
            portion="sec_1",
            text_embedding=source_embedding,
        )
        ContentChunk.objects.create(
            document=target,
            type="provision",
            text="target",
            portion="sec_1",
            title="Target section",
            text_embedding=source_embedding,
        )
        ContentChunk.objects.create(
            document=unrelated,
            type="provision",
            text="unrelated",
            portion="sec_1",
            title="Unrelated section",
            text_embedding=[0.0, 1.0] + [0.0] * 1022,
        )

        request = RequestFactory().get("/")
        view = DocumentProvisionSimilarView()
        view.setup(
            request,
            frbr_uri=source.expression_frbr_uri,
            provision_eid="sec_1",
        )
        view.form = view.get_form()
        view.form.is_valid()

        self.assertEqual(
            [target.pk],
            list(view.get_base_queryset().values_list("pk", flat=True)),
        )

        documents = view.get_queryset()

        self.assertEqual([target.pk], [document.pk for document in documents])
        self.assertEqual("Target section", documents[0].provisions[0].title)
        self.assertEqual(target, documents[0].provisions[0].document)
