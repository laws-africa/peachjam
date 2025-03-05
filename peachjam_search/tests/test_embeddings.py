from django.test import TestCase  # noqa

from peachjam_search.embeddings import make_content_chunks


class TestEmbeddings(TestCase):
    maxDiff = None

    numbers = "one two three four five six seven eight nine ten".split()

    def test_make_content_chunks_text_simple(self):
        self.assertEqual(
            [{"chunk_n": 0, "n_chunks": 1, "text": "simple text", "type": "text"}],
            make_content_chunks("simple text"),
        )

    def test_make_content_chunks_text(self):
        self.assertEqual(
            [
                {
                    "chunk_n": 0,
                    "n_chunks": 7,
                    "text": "one. two. three.",
                    "type": "text",
                },
                {
                    "chunk_n": 1,
                    "n_chunks": 7,
                    "text": "four. five. six.",
                    "type": "text",
                },
                {
                    "chunk_n": 2,
                    "n_chunks": 7,
                    "text": "seven. eight. nine.",
                    "type": "text",
                },
                {"chunk_n": 3, "n_chunks": 7, "text": "ten. one. two.", "type": "text"},
                {
                    "chunk_n": 4,
                    "n_chunks": 7,
                    "text": "three. four. five.",
                    "type": "text",
                },
                {
                    "chunk_n": 5,
                    "n_chunks": 7,
                    "text": "six. seven. eight.",
                    "type": "text",
                },
                {"chunk_n": 6, "n_chunks": 7, "text": "nine. ten.", "type": "text"},
            ],
            make_content_chunks(". ".join(self.numbers * 2) + ".", 10),
        )

    def test_make_content_chunks_pages_simple(self):
        self.assertEqual(
            [
                {
                    "chunk_n": 0,
                    "n_chunks": 1,
                    "portion": 1,
                    "text": "one",
                    "type": "page",
                },
                {
                    "chunk_n": 0,
                    "n_chunks": 1,
                    "portion": 2,
                    "text": "two",
                    "type": "page",
                },
            ],
            make_content_chunks("one\ftwo"),
        )

    def test_make_content_chunks_pages(self):
        # from the list of numbers, create two pages of text separated with `\f`
        pages = "\f".join(
            ". ".join(self.numbers[i : i + 3]) for i in range(0, len(self.numbers), 3)
        )

        self.assertEqual(
            [
                {
                    "chunk_n": 0,
                    "n_chunks": 1,
                    "portion": 1,
                    "text": "one. two. three",
                    "type": "page",
                },
                {
                    "chunk_n": 0,
                    "n_chunks": 1,
                    "portion": 2,
                    "text": "four. five. six",
                    "type": "page",
                },
                {
                    "chunk_n": 0,
                    "n_chunks": 1,
                    "portion": 3,
                    "text": "seven. eight. nine",
                    "type": "page",
                },
                {
                    "chunk_n": 0,
                    "n_chunks": 1,
                    "portion": 4,
                    "text": "ten",
                    "type": "page",
                },
            ],
            make_content_chunks(pages, 10),
        )
