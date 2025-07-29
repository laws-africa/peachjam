from django.test import TestCase
from lxml import etree

from peachjam.adapters import GitbookAdapter
from peachjam.models import Book
from peachjam.xmlutils import parse_html_str


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
                    "id": "unit-1-adm",
                    "title": "Unit 1: Administration of Law",
                    "path": "unit-1-administration-of-law.md",
                    "children": [],
                },
                {
                    "id": "unit-2-the",
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
                "id": "unit-1-adm",
                "title": "Unit 1: Administration of Law",
                "path": "unit-1-administration-of-law.md",
                "children": [],
            },
            {
                "id": "unit-2-the",
                "title": "Unit 2: The Composition of Courts",
                "path": "unit-2-the-composition-of-courts.md",
                "children": [],
            },
        ]

        def content(file_path):
            return f"""
# Contents for {file_path}

Hello :)

## Subheading
""".encode(
                "utf-8"
            )

        self.adapter.get_repo_file = content
        self.adapter.compile_pages(book, toc, "book1")

        self.assertHTMLEqual(
            """<div id="unit-1-adm">
<div>
<h1 id="unit-1-adm--contents-for-book1unit-1-administration-of-law.md">
Contents for book1/unit-1-administration-of-law.md
</h1><p>
Hello :)
</p><h2 id="unit-1-adm--subheading">
Subheading
</h2>
</div>
</div><div id="unit-2-the">
<div>
<h1 id="unit-2-the--contents-for-book1unit-2-the-composition-of-courts.md">
Contents for book1/unit-2-the-composition-of-courts.md
</h1><p>
Hello :)
</p><h2 id="unit-2-the--subheading">
Subheading
</h2>
</div>
</div>""",
            book.content_html,
        )

        self.assertEqual(
            [
                {
                    "id": "unit-1-adm",
                    "title": "Unit 1: Administration of Law",
                    "path": "unit-1-administration-of-law.md",
                    "children": [
                        {
                            "id": "unit-1-adm--subheading",
                            "title": "Subheading",
                            "type": "h2",
                            "children": [],
                        }
                    ],
                },
                {
                    "id": "unit-2-the",
                    "title": "Unit 2: The Composition of Courts",
                    "path": "unit-2-the-composition-of-courts.md",
                    "children": [
                        {
                            "id": "unit-2-the--subheading",
                            "title": "Subheading",
                            "type": "h2",
                            "children": [],
                        }
                    ],
                },
            ],
            toc,
        )

    def test_rewrite_images(self):
        root = parse_html_str(
            """
<div>
<img src=".gitbook/assets/foo.png">
<img src="../.gitbook/assets/bar.png">
</div>
"""
        )
        self.adapter.munge_page_html({"id": "test"}, root)

        self.assertHTMLEqual(
            """
<div>
<img src="media/foo.png">
<img src="media/bar.png">
</div>
""",
            etree.tostring(root, encoding="unicode"),
        )
