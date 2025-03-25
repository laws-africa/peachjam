from datetime import date
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase

from peachjam.models import Country, DocumentContent, GenericDocument, Language
from peachjam_ml.models import ContentChunk, DocumentEmbedding


class TestContentChunks(TestCase):
    maxDiff = None
    fixtures = ["tests/users", "tests/countries", "tests/languages"]

    numbers = "one two three four five six seven eight nine ten".split()

    def setUp(self):
        self.document = GenericDocument.objects.create(
            jurisdiction=Country.objects.first(),
            title="Test",
            date=date.today(),
            language=Language.objects.first(),
            frbr_uri_doctype="doc",
            frbr_uri_number="test",
            frbr_uri_date="2024",
        )

    def test_make_content_chunks_text_simple(self):
        self.assertEqual(
            [
                {
                    "type": "text",
                    "text": "simple text",
                    "portion": None,
                    "chunk_n": 0,
                    "n_chunks": 1,
                    "text_embedding": None,
                    "parent_ids": None,
                    "parent_titles": None,
                    "provision_type": None,
                    "title": None,
                }
            ],
            [
                c.as_dict_for_es()
                for c in ContentChunk.split_chunks(
                    [
                        ContentChunk(
                            document=self.document, type="text", text="simple text"
                        )
                    ]
                )
            ],
        )

    def test_make_content_chunks_text(self):
        self.assertEqual(
            [
                {
                    "type": "text",
                    "text": "one. two. three.",
                    "portion": None,
                    "chunk_n": 0,
                    "n_chunks": 7,
                    "text_embedding": None,
                    "parent_ids": None,
                    "parent_titles": None,
                    "provision_type": None,
                    "title": None,
                },
                {
                    "type": "text",
                    "text": "four. five. six.",
                    "portion": None,
                    "chunk_n": 1,
                    "n_chunks": 7,
                    "text_embedding": None,
                    "parent_ids": None,
                    "parent_titles": None,
                    "provision_type": None,
                    "title": None,
                },
                {
                    "type": "text",
                    "text": "seven. eight. nine.",
                    "portion": None,
                    "chunk_n": 2,
                    "n_chunks": 7,
                    "text_embedding": None,
                    "parent_ids": None,
                    "parent_titles": None,
                    "provision_type": None,
                    "title": None,
                },
                {
                    "type": "text",
                    "text": "ten. one. two.",
                    "portion": None,
                    "chunk_n": 3,
                    "n_chunks": 7,
                    "text_embedding": None,
                    "parent_ids": None,
                    "parent_titles": None,
                    "provision_type": None,
                    "title": None,
                },
                {
                    "type": "text",
                    "text": "three. four. five.",
                    "portion": None,
                    "chunk_n": 4,
                    "n_chunks": 7,
                    "text_embedding": None,
                    "parent_ids": None,
                    "parent_titles": None,
                    "provision_type": None,
                    "title": None,
                },
                {
                    "type": "text",
                    "text": "six. seven. eight.",
                    "portion": None,
                    "chunk_n": 5,
                    "n_chunks": 7,
                    "text_embedding": None,
                    "parent_ids": None,
                    "parent_titles": None,
                    "provision_type": None,
                    "title": None,
                },
                {
                    "type": "text",
                    "text": "nine. ten.",
                    "portion": None,
                    "chunk_n": 6,
                    "n_chunks": 7,
                    "text_embedding": None,
                    "parent_ids": None,
                    "parent_titles": None,
                    "provision_type": None,
                    "title": None,
                },
            ],
            [
                c.as_dict_for_es()
                for c in ContentChunk.split_chunks(
                    [
                        ContentChunk(
                            document=self.document,
                            type="text",
                            text=". ".join(self.numbers * 2) + ".",
                        )
                    ],
                    10,
                )
            ],
        )

    def test_make_content_chunks_pages(self):
        # from the list of numbers, create two pages of text separated with `\f`
        pages = [
            ". ".join(self.numbers[i : i + 3]) for i in range(0, len(self.numbers), 3)
        ]
        chunks = [
            ContentChunk(document=self.document, type="page", text=text, portion=i + 1)
            for i, text in enumerate(pages)
        ]
        split_chunks = ContentChunk.split_chunks(chunks, 10)

        self.assertEqual(
            [
                {
                    "type": "page",
                    "text": "one. two. three",
                    "portion": 1,
                    "chunk_n": 0,
                    "n_chunks": 1,
                    "text_embedding": None,
                    "parent_ids": None,
                    "parent_titles": None,
                    "provision_type": None,
                    "title": None,
                },
                {
                    "type": "page",
                    "text": "four. five. six",
                    "portion": 2,
                    "chunk_n": 0,
                    "n_chunks": 1,
                    "text_embedding": None,
                    "parent_ids": None,
                    "parent_titles": None,
                    "provision_type": None,
                    "title": None,
                },
                {
                    "type": "page",
                    "text": "seven. eight. nine",
                    "portion": 3,
                    "chunk_n": 0,
                    "n_chunks": 1,
                    "text_embedding": None,
                    "parent_ids": None,
                    "parent_titles": None,
                    "provision_type": None,
                    "title": None,
                },
                {
                    "type": "page",
                    "text": "ten",
                    "portion": 4,
                    "chunk_n": 0,
                    "n_chunks": 1,
                    "text_embedding": None,
                    "parent_ids": None,
                    "parent_titles": None,
                    "provision_type": None,
                    "title": None,
                },
            ],
            [c.as_dict_for_es() for c in split_chunks],
        )

    @patch("peachjam_ml.models.get_text_embedding_batch")
    def test_refresh_for_document(self, mock_get_text_embedding_batch):
        mock_get_text_embedding_batch.return_value = [[0.1] * 1024]

        DocumentContent.objects.create(
            document=self.document, content_text="one two three"
        )

        # these should be deleted
        ContentChunk.objects.create(
            document=self.document, text="bad", type="text", text_embedding=[0.1] * 1024
        )

        settings.PEACHJAM["SEARCH_SEMANTIC"] = True
        try:
            de = DocumentEmbedding.refresh_for_document(self.document)

            # Verify
            self.assertTrue(mock_get_text_embedding_batch.called)
            chunks = ContentChunk.objects.filter(document=self.document)
            self.assertEqual(["one two three"], [c.text for c in chunks])
            self.assertEqual(len(chunks), 1)
            self.assertEqual([0.031249847] * 1024, de.text_embedding)
        finally:
            settings.PEACHJAM["SEARCH_SEMANTIC"] = False
