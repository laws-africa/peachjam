import os.path

from django.test import TestCase

from peachjam.helpers import chunks, pdfjs_to_text, qualify_local_refs


class HelpersTestCase(TestCase):
    def test_pdfjs_to_text(self):
        fname = os.path.join(
            os.path.dirname(__file__), "../fixtures/tests/citations.pdf"
        )
        text = pdfjs_to_text(fname)
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
            text,
        )

    def test_chunks(self):
        self.assertEqual(
            chunks([1, 2, 3, 4, 5, 6, 7, 8, 9], 3), [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        )
        self.assertEqual(
            chunks([1, 2, 3, 4, 5, 6, 7, 8], 3), [[1, 2, 3], [4, 5, 6], [7, 8]]
        )
        self.assertEqual(chunks([1, 2, 3, 4], 3), [[1, 2], [3], [4]])
        self.assertEqual(chunks([1, 2], 5), [[1], [2]])
        self.assertEqual(chunks([1, 2], 2), [[1], [2]])
        self.assertEqual(chunks([], 3), [])

    def test_qualify_local_refs_rewrites_fragment_local_links(self):
        html = (
            '<span><a class="akn-ref" href="#sec_2" data-href="#sec_2">'
            "Section 2"
            "</a></span>"
        )
        result = qualify_local_refs(html, "/akn/za/act/2000/1/eng@2024-01-01")

        self.assertIn('href="/akn/za/act/2000/1/eng@2024-01-01#sec_2"', result)
        self.assertIn('data-href="/akn/za/act/2000/1/eng@2024-01-01#sec_2"', result)

    def test_qualify_local_refs_leaves_non_local_links_unchanged(self):
        html = (
            '<p><a href="#">Top</a></p>' '<p><a href="/akn/za/act/2000/1">Act</a></p>'
        )
        result = qualify_local_refs(html, "/akn/za/act/2000/1/eng@2024-01-01")

        self.assertIn('href="#"', result)
        self.assertIn('href="/akn/za/act/2000/1"', result)
