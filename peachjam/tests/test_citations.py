import os
from datetime import datetime

from countries_plus.models import Country
from django.core.files.base import File
from django.test import TestCase
from languages_plus.models import Language

from peachjam.analysis.citations import citation_analyser
from peachjam.models import CoreDocument, SourceFile


class CitationAnalyserTestCase(TestCase):
    fixtures = ["tests/countries", "tests/languages"]
    maxDiff = None

    def test_pdf_to_text(self):
        self.assertEqual(
            """Test document for extracting citations
This is page 1
Recalling its Resolution ACHPR/Res.79 (XXXVIII) 05 on the Composition and
Operationalization of the Working Group on the Death Penalty, and
Resolution ACHPR/Res.227 (LII) 2012 on the Expansion of the Mandate of the
Working Group on Death Penalty in Africa, to include Extra-Judicial, Summary or
Arbitrary Killings in Africa;This is page 2
Further recalling its decision to appoint a Special Rapporteur on Prisons and
Conditions of Detention in Africa at its 20th Ordinary Session held from 21 to 31
October 1996, as well as Resolution ACHPR/Res.306 (EXT.OS/ XVIII) 2015
Expanding the Mandate of the Special Rapporteur on Prisons and Conditions of
Detention in Africa to include issues relating to policing and human rights;""",
            citation_analyser.pdf_to_text(
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "fixtures",
                    "tests",
                    "citations.pdf",
                ),
            ),
        )

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
