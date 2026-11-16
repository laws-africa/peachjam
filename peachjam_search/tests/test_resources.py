from types import SimpleNamespace

from django.test import SimpleTestCase

from peachjam.models import Author
from peachjam_search.resources import SearchResultsDownloadResource


class SearchResultsDownloadResourceTest(SimpleTestCase):
    def test_dehydrate_single_author(self):
        author = Author(name="National Assembly", code="national-assembly")
        document = SimpleNamespace(author=author)

        value = SearchResultsDownloadResource().dehydrate_author(document)

        self.assertEqual("National Assembly", value)
