import os
from datetime import datetime

from countries_plus.models import Country
from django.core.files.base import File
from django.test import TestCase
from languages_plus.models import Language

from peachjam.analysis.citations import citation_analyser
from peachjam.models import (
    CoreDocument,
    DocumentNature,
    ProvisionCitation,
    ProvisionCitationCount,
    SourceFile,
    Work,
)


class CitationAnalyserTestCase(TestCase):
    fixtures = ["tests/countries", "tests/languages"]
    maxDiff = None

    def test_pdf_extractions(self):
        # only some installations have matchers set up
        if not citation_analyser.matchers:
            return

        doc = CoreDocument.objects.create(
            title="test",
            frbr_uri_doctype="doc",
            frbr_uri_number="test",
            jurisdiction=Country.objects.get(pk="ZA"),
            language=Language.objects.get(pk="en"),
            date=datetime(2023, 1, 1),
        )

        with open(
            os.path.join(
                os.path.dirname(__file__), "..", "fixtures", "tests", "citations.pdf"
            ),
            "rb",
        ) as f:
            doc.source_file = SourceFile(
                filename="citations.pdf",
                file=File(f),
            )
            doc.source_file.save()
            citation_analyser.extract_citations_from_source_file(doc)

        self.assertEquals(
            [
                {
                    "target_id": "page-1",
                    "target_selectors": [
                        {"end": 102, "start": 77, "type": "TextPositionSelector"},
                        {
                            "exact": "ACHPR/Res.79 (XXXVIII) 05",
                            "prefix": "ge 1Recalling its Resolution ",
                            "suffix": " on the Composition andOperat",
                            "type": "TextQuoteSelector",
                        },
                    ],
                    "text": "ACHPR/Res.79 (XXXVIII) 05",
                    "url": "/akn/aa-au/statement/resolution/achpr/2005/79",
                },
                {
                    "target_id": "page-1",
                    "target_selectors": [
                        {"end": 225, "start": 201, "type": "TextPositionSelector"},
                        {
                            "exact": "ACHPR/Res.227 (LII) 2012",
                            "prefix": "Death Penalty, andResolution ",
                            "suffix": " on the Expansion of the Manda",
                            "type": "TextQuoteSelector",
                        },
                    ],
                    "text": "ACHPR/Res.227 (LII) 2012",
                    "url": "/akn/aa-au/statement/resolution/achpr/2012/227",
                },
                {
                    "target_id": "page-2",
                    "target_selectors": [
                        {"end": 242, "start": 208, "type": "TextPositionSelector"},
                        {
                            "exact": "ACHPR/Res.306 (EXT.OS/ XVIII) 2015",
                            "prefix": "r 1996, as well as Resolution ",
                            "suffix": "Expanding the Mandate of the ",
                            "type": "TextQuoteSelector",
                        },
                    ],
                    "text": "ACHPR/Res.306 (EXT.OS/ XVIII) 2015",
                    "url": "/akn/aa-au/statement/resolution/achpr/2015/306",
                },
            ],
            [
                {
                    "text": x.text,
                    "url": x.url,
                    "target_id": x.target_id,
                    "target_selectors": x.target_selectors,
                }
                for x in doc.citation_links.all()
            ],
        )

    def test_delete_citations(self):
        doc = CoreDocument(
            content_html_is_akn=False,
            content_html="""
<div>
<p>Some text <a href="/akn/ke/act/2010/1">Act 1 of 2010</a></p>
<p>Some text <a href="https://example.com">Example</a></p>
</div>
""",
        )
        doc.delete_citations()
        self.assertEqual(
            """<div>
<p>Some text Act 1 of 2010</p>
<p>Some text <a href="https://example.com">Example</a></p>
</div>
""",
            doc.content_html,
        )

    def test_delete_citations_should_not_change_akn(self):
        doc = CoreDocument(
            content_html_is_akn=True,
            content_html="""
<div>
<p>Some text <a href="/akn/ke/act/2010/1">Act 1 of 2010</a></p>
<p>Some text <a href="https://example.com">Example</a></p>
</div>
""",
        )
        doc.delete_citations()
        self.assertEqual(
            """
<div>
<p>Some text <a href="/akn/ke/act/2010/1">Act 1 of 2010</a></p>
<p>Some text <a href="https://example.com">Example</a></p>
</div>
""",
            doc.content_html,
        )


class ProvisionCitationCountTests(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def setUp(self):
        self.language = Language.objects.get(pk="en")
        self.country = Country.objects.get(pk="ZA")
        self.nature, _ = DocumentNature.objects.get_or_create(
            code="act", defaults={"name": "Act"}
        )

    def make_work(self, number):
        return Work.objects.create(
            title=f"Work {number}",
            frbr_uri=f"/akn/za/act/2020/{number}",
        )

    def make_document(self, work, expression_suffix):
        number = work.frbr_uri.split("/")[-1]
        return CoreDocument.objects.create(
            work=work,
            title=f"Doc {expression_suffix}",
            date=datetime(2020, 1, 1),
            language=self.language,
            jurisdiction=self.country,
            nature=self.nature,
            work_frbr_uri=work.frbr_uri,
            frbr_uri_doctype="act",
            frbr_uri_date="2020",
            frbr_uri_number=number,
            expression_frbr_uri=f"{work.frbr_uri}@eng@{expression_suffix}",
        )

    def test_refresh_for_works_populates_counts(self):
        target_work = self.make_work(100)
        citing_doc_one = self.make_document(self.make_work(200), 1)
        citing_doc_two = self.make_document(self.make_work(201), 2)

        # stale count that should be replaced
        ProvisionCitationCount.objects.create(
            work=target_work, provision_eid="p-1", count=99
        )

        ProvisionCitation.objects.create(
            work=target_work,
            provision_eid="p-1",
            citing_document=citing_doc_one,
        )
        ProvisionCitation.objects.create(
            work=target_work,
            provision_eid="p-1",
            citing_document=citing_doc_one,
        )
        ProvisionCitation.objects.create(
            work=target_work,
            provision_eid="p-1",
            citing_document=citing_doc_two,
        )
        ProvisionCitation.objects.create(
            work=target_work,
            provision_eid="p-2",
            citing_document=citing_doc_one,
        )

        ProvisionCitationCount.refresh_for_works({target_work.id, None})

        counts = {
            c.provision_eid: c.count
            for c in ProvisionCitationCount.objects.filter(work=target_work)
        }
        self.assertEqual({"p-1": 2, "p-2": 1}, counts)

    def test_refresh_only_updates_requested_work(self):
        target_work = self.make_work(300)
        other_work = self.make_work(400)

        target_doc = self.make_document(self.make_work(301), 3)
        other_doc = self.make_document(self.make_work(401), 4)

        ProvisionCitation.objects.create(
            work=target_work, provision_eid="p-1", citing_document=target_doc
        )
        ProvisionCitation.objects.create(
            work=other_work, provision_eid="p-2", citing_document=other_doc
        )

        ProvisionCitationCount.objects.create(
            work=other_work, provision_eid="p-2", count=5
        )

        ProvisionCitationCount.refresh_for_works([target_work.id])

        target_counts = ProvisionCitationCount.objects.filter(work=target_work)
        self.assertEqual(1, target_counts.count())
        self.assertEqual(1, target_counts.first().count)

        other_count = ProvisionCitationCount.objects.get(
            work=other_work, provision_eid="p-2"
        )
        self.assertEqual(5, other_count.count)
