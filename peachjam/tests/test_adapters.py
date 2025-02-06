from django.test import TestCase

from peachjam.adapters import IndigoAdapter


class IndigoAdapterTest(TestCase):
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
