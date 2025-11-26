from django.test import TestCase

from peachjam.adapters import IndigoAdapter
from peachjam.models import Taxonomy


class IndigoAdapterTest(TestCase):
    maxDiff = None

    def setUp(self):
        self.adapter = IndigoAdapter(
            None,
            {"token": "XXX", "api_url": "http://example.com", "places": "za za-cpt"},
        )
        self.adapter.place_codes = ["za", "za-cpt"]

    def test_is_responsible_for_places(self):
        self.assertTrue(self.adapter.is_responsible_for("/akn/za/act/2009/1"))
        self.assertTrue(self.adapter.is_responsible_for("/akn/za-cpt/act/2009/1"))

        self.assertFalse(self.adapter.is_responsible_for("/akn/bw/act/2009/1"))
        self.assertFalse(self.adapter.is_responsible_for("/akn/za-xxx/act/2009/1"))

    def test_is_responsible_for_include_doctypes(self):
        self.adapter.include_doctypes = ["act"]

        self.assertTrue(self.adapter.is_responsible_for("/akn/za/act/2009/1"))
        self.assertTrue(self.adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertFalse(
            self.adapter.is_responsible_for("/akn/za/judgment/zahc/1999/1")
        )

    def test_is_responsible_for_exclude_doctypes(self):
        self.adapter.exclude_doctypes = ["act"]

        self.assertFalse(self.adapter.is_responsible_for("/akn/za/act/2009/1"))
        self.assertFalse(self.adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertTrue(self.adapter.is_responsible_for("/akn/za/judgment/zahc/1999/1"))

    def test_is_responsible_for_include_subtypes(self):
        self.adapter.include_subtypes = ["by-law"]

        self.assertFalse(self.adapter.is_responsible_for("/akn/za/act/2009/1"))
        self.assertTrue(self.adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertFalse(self.adapter.is_responsible_for("/akn/za/act/thing/1999/1"))

    def test_is_responsible_for_exclude_subtypes(self):
        self.adapter.exclude_subtypes = ["by-law"]

        self.assertTrue(self.adapter.is_responsible_for("/akn/za/act/2009/1"))
        self.assertFalse(self.adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertTrue(self.adapter.is_responsible_for("/akn/za/act/thing/1999/1"))

    def test_is_responsible_for_include_actors(self):
        self.adapter.include_actors = ["foo"]

        self.assertTrue(
            self.adapter.is_responsible_for("/akn/za/act/by-law/foo/2009/1")
        )
        self.assertFalse(self.adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertFalse(
            self.adapter.is_responsible_for("/akn/za/act/by-law/bar/1999/1")
        )

    def test_is_responsible_for_exclude_actors(self):
        self.adapter.exclude_actors = ["foo"]

        self.assertFalse(
            self.adapter.is_responsible_for("/akn/za/act/by-law/foo/2009/1")
        )
        self.assertTrue(self.adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertTrue(
            self.adapter.is_responsible_for("/akn/za/act/by-law/bar/1999/1")
        )

    def test_import_taxonomy_tree(self):
        self.adapter.taxonomy_topic_root = "src1:dest1 src2:dest2"

        src_tree = [
            {
                "name": "src1",
                "slug": "src1",
                "children": [
                    {
                        "name": "child-1",
                        "slug": "src1-child-1",
                        "children": [],
                    },
                    {
                        "name": "child-2",
                        "slug": "src1-child-2",
                        "children": [],
                    },
                ],
            },
            {
                "name": "src2",
                "slug": "src2",
                "children": [
                    {
                        "name": "child-a",
                        "slug": "src2-child-a",
                        "children": [],
                    },
                    {
                        "name": "child-b",
                        "slug": "src2-child-b",
                        "children": [],
                    },
                ],
            },
        ]
        self.adapter.get_taxonomy_tree = lambda: src_tree

        # pre-populate dest1 and dest2 locally
        Taxonomy.load_bulk(
            [
                {
                    "data": {
                        "name": "dest1",
                        "slug": "dest1",
                    },
                    "children": [],
                },
                {
                    "data": {
                        "name": "dest2",
                        "slug": "dest2",
                    },
                    "children": [
                        {
                            "data": {
                                "name": "child-a",
                                "slug": "dest2-child-a",
                            },
                        },
                        {
                            # this must be deleted
                            "data": {
                                "name": "child-z",
                                "slug": "dest2-child-z",
                            }
                        },
                    ],
                },
            ]
        )

        # dest1 will be empty locally, and dest2 will have some topics and some which must be deleted
        src_mapping, tree_mapping = self.adapter.import_taxonomy_tree()

        self.assertEqual(
            {
                "src1": "dest1",
                "src2": "dest2",
            },
            src_mapping,
        )

        self.assertEqual(
            {
                "src1-child-1": Taxonomy.objects.get(slug="dest1-child-1"),
                "src1-child-2": Taxonomy.objects.get(slug="dest1-child-2"),
                "src2-child-a": Taxonomy.objects.get(slug="dest2-child-a"),
                "src2-child-b": Taxonomy.objects.get(slug="dest2-child-b"),
            },
            tree_mapping,
        )

        def simplify(entries):
            # keep only necessary data fields for comparison
            for entry in entries:
                entry["data"] = {
                    k: v for k, v in entry["data"].items() if k in ["name", "slug"]
                }
                simplify(entry.get("children", []))

        local_tree = Taxonomy.dump_bulk(
            parent=Taxonomy.objects.get(slug="dest1"), keep_ids=False
        )
        simplify(local_tree)
        self.assertEqual(
            [
                {
                    "data": {
                        "name": "dest1",
                        "slug": "dest1",
                    },
                    "children": [
                        {
                            "data": {
                                "name": "child-1",
                                "slug": "dest1-child-1",
                            }
                        },
                        {
                            "data": {
                                "name": "child-2",
                                "slug": "dest1-child-2",
                            }
                        },
                    ],
                }
            ],
            local_tree,
        )

        local_tree = Taxonomy.dump_bulk(
            parent=Taxonomy.objects.get(slug="dest2"), keep_ids=False
        )
        simplify(local_tree)
        self.assertEqual(
            [
                {
                    "data": {
                        "name": "dest2",
                        "slug": "dest2",
                    },
                    "children": [
                        {
                            "data": {
                                "name": "child-a",
                                "slug": "dest2-child-a",
                            }
                        },
                        {
                            "data": {
                                "name": "child-b",
                                "slug": "dest2-child-b",
                            }
                        },
                    ],
                }
            ],
            local_tree,
        )
