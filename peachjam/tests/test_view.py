import datetime

from countries_plus.models import Country
from django_webtest import WebTest
from languages_plus.models import Language

from peachjam.models import Author, Judgment


class PeachjamViewsTestCase(WebTest):

    fixtures = ["tests/authors", "tests/countries", "tests/languages"]

    def test_homepage(self):
        home = self.app.get("/")
        assert home.status == "200 OK"

    def test_pdf_source(self):
        j = Judgment(
            language=Language.objects.get(pk="en"),
            author=Author.objects.first(),
            date=datetime.date(2019, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Foo v Bar",
        )
        j.save()
        url = f"{j.expression_frbr_uri}/souce.pdf"
        document_source = self.app.get(url)
        print("==>", document_source.status)
        # document_source.status == '404 Not Found'
