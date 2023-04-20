from cobalt import FrbrUri
from django.test import TestCase

from peachjam.views.documents import RedirectResolver

urls = [
    "/akn/zm/judgment/zmsc/2021/7/eng@2021-01-19",
    "/akn/ug/judgment/ughc/2020/219/eng@2020-05-08",
    "/akn/za-gp/judgment/zagpjhc/2023/317/eng@2023-04-17",
    "/akn/za/judgment/zagpjhc/2023/345/eng@2023-04-17",
    "/akn/tz/judgment/tzhccomd/2023/83/eng@2023-03-27",
    "/akn/tz-znz/judgment/tzznzhc/2023/18/eng@2023-02-14",
    "/akn/aa-au/judgment/eacj/2023/5/eng@2023-02-27",
]


class TestRedirectResolver(TestCase):
    def test_resolver_africanlii(self):
        resolver = RedirectResolver("africanlii")
        domains = [
            "new.zambialii.org",
            "new.ulii.org",
            "lawlibrary.org.za",
            "lawlibrary.org.za",
            "new.tanzlii.org",
            "zanzibarlii.org",
            None,
        ]
        results = zip(urls, domains)

        for result in results:
            with self.subTest(f"africanlii > {result[0]}"):
                parsed_frbr_url = FrbrUri.parse(result[0])
                url = resolver.get_domain_for_frbr_uri(parsed_frbr_url)
                self.assertEqual(result[1], url)

    def test_resolver_zanzibarlii(self):
        resolver = RedirectResolver("zanzibarlii")

        domains = [
            "new.zambialii.org",
            "new.ulii.org",
            "lawlibrary.org.za",
            "lawlibrary.org.za",
            "new.tanzlii.org",
            None,
            "agp.africanlii.org",
        ]
        results = zip(urls, domains)
        for result in results:
            with self.subTest(f"zanzibarlii > {result[0]}"):
                parsed_frbr_url = FrbrUri.parse(result[0])
                url = resolver.get_domain_for_frbr_uri(parsed_frbr_url)
                self.assertEqual(result[1], url)

    def test_resolver_tanzlii(self):
        resolver = RedirectResolver("tanzlii")

        domains = [
            "new.zambialii.org",
            "new.ulii.org",
            "lawlibrary.org.za",
            "lawlibrary.org.za",
            None,
            "zanzibarlii.org",
            "agp.africanlii.org",
        ]
        results = zip(urls, domains)
        for result in results:
            with self.subTest(f"tanzlii > {result[0]}"):
                parsed_frbr_url = FrbrUri.parse(result[0])
                url = resolver.get_domain_for_frbr_uri(parsed_frbr_url)
                self.assertEqual(result[1], url)
