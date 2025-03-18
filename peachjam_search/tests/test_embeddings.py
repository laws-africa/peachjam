from django.test import TestCase  # noqa

from peachjam_search.embeddings import ContentChunk, split_chunks


class TestEmbeddings(TestCase):
    maxDiff = None

    numbers = "one two three four five six seven eight nine ten".split()

    def test_make_content_chunks_text_simple(self):
        self.assertEqual(
            [ContentChunk("text", "simple text")],
            split_chunks([ContentChunk("text", "simple text")]),
        )

    def test_make_content_chunks_text(self):
        self.assertEqual(
            [
                ContentChunk("text", "one. two. three.", chunk_n=0, n_chunks=7),
                ContentChunk("text", "four. five. six.", chunk_n=1, n_chunks=7),
                ContentChunk("text", "seven. eight. nine.", chunk_n=2, n_chunks=7),
                ContentChunk("text", "ten. one. two.", chunk_n=3, n_chunks=7),
                ContentChunk("text", "three. four. five.", chunk_n=4, n_chunks=7),
                ContentChunk("text", "six. seven. eight.", chunk_n=5, n_chunks=7),
                ContentChunk("text", "nine. ten.", chunk_n=6, n_chunks=7),
            ],
            split_chunks([ContentChunk("text", ". ".join(self.numbers * 2) + ".")], 10),
        )

    def test_make_content_chunks_pages(self):
        # from the list of numbers, create two pages of text separated with `\f`
        pages = [
            ". ".join(self.numbers[i : i + 3]) for i in range(0, len(self.numbers), 3)
        ]
        chunks = [
            ContentChunk("page", text, portion=i + 1) for i, text in enumerate(pages)
        ]

        self.assertEqual(
            [
                ContentChunk(
                    "page", "one. two. three", portion=1, chunk_n=0, n_chunks=1
                ),
                ContentChunk(
                    "page", "four. five. six", portion=2, chunk_n=0, n_chunks=1
                ),
                ContentChunk(
                    "page", "seven. eight. nine", portion=3, chunk_n=0, n_chunks=1
                ),
                ContentChunk("page", "ten", portion=4, chunk_n=0, n_chunks=1),
            ],
            split_chunks(chunks, 10),
        )
