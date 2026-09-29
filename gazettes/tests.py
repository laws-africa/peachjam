from django.test import SimpleTestCase, override_settings
from django.urls import resolve

from gazettes.views import YearView, global_year_not_found
from peachjam.views import GazetteYearView


@override_settings(ROOT_URLCONF="gazettes.urls")
class GazetteYearUrlTest(SimpleTestCase):
    def test_global_year_page_is_disabled(self):
        match = resolve("/gazettes/2024", urlconf="gazettes.urls")

        self.assertEqual(global_year_not_found, match.func)
        self.assertEqual(404, self.client.get("/gazettes/2024").status_code)

    def test_jurisdiction_year_page_is_available(self):
        match = resolve("/gazettes/za/2024", urlconf="gazettes.urls")

        self.assertEqual(YearView, match.func.view_class)

    def test_shared_global_year_page_remains_available(self):
        match = resolve("/gazettes/2024", urlconf="peachjam.urls")

        self.assertEqual(GazetteYearView, match.func.view_class)
