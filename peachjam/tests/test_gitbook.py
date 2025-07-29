from django.test import TestCase

from peachjam.adapters import GitbookAdapter
from peachjam.models import Book


class GitbookAdapterTest(TestCase):
    maxDiff = None

    def setUp(self):
        self.adapter = GitbookAdapter(
            None, {"repo_name": "test", "access_token": "abc123"}
        )

    def test_build_toc(self):
        toc = self.adapter.build_toc(
            """
<h1>Table of contents</h1>
<ul>
<li><a href="README.md">Frontmatter</a></li>
<li><a href="unit-1-administration-of-law.md">Unit 1: Administration of Law</a></li>
<li><a href="unit-2-the-composition-of-courts.md">Unit 2: The Composition of Courts</a></li>
</ul>
"""
        )
        self.assertListEqual(
            [
                {
                    "id": "readme",
                    "title": "Frontmatter",
                    "path": "README.md",
                    "children": [],
                },
                {
                    "id": "unit-1-administration-of-law",
                    "title": "Unit 1: Administration of Law",
                    "path": "unit-1-administration-of-law.md",
                    "children": [],
                },
                {
                    "id": "unit-2-the-composition-of-courts",
                    "title": "Unit 2: The Composition of Courts",
                    "path": "unit-2-the-composition-of-courts.md",
                    "children": [],
                },
            ],
            toc,
        )

    def test_compile_toc(self):
        book = Book()
        toc = [
            {
                "id": "unit-1-administration-of-law",
                "title": "Unit 1: Administration of Law",
                "path": "unit-1-administration-of-law.md",
                "children": [],
            },
            {
                "id": "unit-2-the-composition-of-courts",
                "title": "Unit 2: The Composition of Courts",
                "path": "unit-2-the-composition-of-courts.md",
                "children": [],
            },
        ]

        self.adapter.get_repo_file = (
            lambda file_path: f"# Contents for {file_path}\n\nHello :)".encode("utf-8")
        )
        self.adapter.compile_pages(book, toc, "book1")

        self.assertHTMLEqual(
            """<div id="unit-1-administration-of-law">
<div>
<h1 id="unit-1-administration-of-law--contents-for-book1unit-1-administration-of-law.md">
Contents for book1/unit-1-administration-of-law.md
</h1><p>
Hello :)
</p>
</div>
</div><div id="unit-2-the-composition-of-courts">
<div>
<h1 id="unit-2-the-composition-of-courts--contents-for-book1unit-2-the-composition-of-courts.md">
Contents for book1/unit-2-the-composition-of-courts.md
</h1><p>
Hello :)
</p>
</div>
</div>""",
            book.content_html,
        )
