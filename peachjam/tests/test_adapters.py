from django.test import TestCase

from peachjam.adapters import IndigoAdapter


class IndigoAdapterTest(TestCase):
    def test_is_responsible_for_places(self):
        adapter = IndigoAdapter(
            None,
            {"token": "XXX", "api_url": "http://example.com", "places": "za za-cpt"},
        )
        # force place codes
        adapter.place_codes = ["za", "za-cpt"]

        self.assertTrue(adapter.is_responsible_for("/akn/za/act/2009/1"))
        self.assertTrue(adapter.is_responsible_for("/akn/za-cpt/act/2009/1"))

        self.assertFalse(adapter.is_responsible_for("/akn/bw/act/2009/1"))
        self.assertFalse(adapter.is_responsible_for("/akn/za-xxx/act/2009/1"))

    def test_is_responsible_for_include_doctypes(self):
        adapter = IndigoAdapter(
            None,
            {
                "token": "XXX",
                "api_url": "http://example.com",
                "places": "za za-cpt",
                "include_doctypes": "act",
            },
        )
        # force place codes
        adapter.place_codes = ["za", "za-cpt"]

        self.assertTrue(adapter.is_responsible_for("/akn/za/act/2009/1"))
        self.assertTrue(adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertFalse(adapter.is_responsible_for("/akn/za/judgment/zahc/1999/1"))

    def test_is_responsible_for_exclude_doctypes(self):
        adapter = IndigoAdapter(
            None,
            {
                "token": "XXX",
                "api_url": "http://example.com",
                "places": "za za-cpt",
                "exclude_doctypes": "act",
            },
        )
        # force place codes
        adapter.place_codes = ["za", "za-cpt"]

        self.assertFalse(adapter.is_responsible_for("/akn/za/act/2009/1"))
        self.assertFalse(adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertTrue(adapter.is_responsible_for("/akn/za/judgment/zahc/1999/1"))

    def test_is_responsible_for_include_subtypes(self):
        adapter = IndigoAdapter(
            None,
            {
                "token": "XXX",
                "api_url": "http://example.com",
                "places": "za za-cpt",
                "include_subtypes": "by-law",
            },
        )
        # force place codes
        adapter.place_codes = ["za", "za-cpt"]

        self.assertFalse(adapter.is_responsible_for("/akn/za/act/2009/1"))
        self.assertTrue(adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertFalse(adapter.is_responsible_for("/akn/za/act/thing/1999/1"))

    def test_is_responsible_for_exclude_subtypes(self):
        adapter = IndigoAdapter(
            None,
            {
                "token": "XXX",
                "api_url": "http://example.com",
                "places": "za za-cpt",
                "exclude_subtypes": "by-law",
            },
        )
        # force place codes
        adapter.place_codes = ["za", "za-cpt"]

        self.assertTrue(adapter.is_responsible_for("/akn/za/act/2009/1"))
        self.assertFalse(adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertTrue(adapter.is_responsible_for("/akn/za/act/thing/1999/1"))

    def test_is_responsible_for_include_actors(self):
        adapter = IndigoAdapter(
            None,
            {
                "token": "XXX",
                "api_url": "http://example.com",
                "places": "za za-cpt",
                "include_actors": "foo",
            },
        )
        # force place codes
        adapter.place_codes = ["za", "za-cpt"]

        self.assertTrue(adapter.is_responsible_for("/akn/za/act/by-law/foo/2009/1"))
        self.assertFalse(adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertFalse(adapter.is_responsible_for("/akn/za/act/by-law/bar/1999/1"))

    def test_is_responsible_for_exclude_actors(self):
        adapter = IndigoAdapter(
            None,
            {
                "token": "XXX",
                "api_url": "http://example.com",
                "places": "za za-cpt",
                "exclude_actors": "foo",
            },
        )
        # force place codes
        adapter.place_codes = ["za", "za-cpt"]

        self.assertFalse(adapter.is_responsible_for("/akn/za/act/by-law/foo/2009/1"))
        self.assertTrue(adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertTrue(adapter.is_responsible_for("/akn/za/act/by-law/bar/1999/1"))
