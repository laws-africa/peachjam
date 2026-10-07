from urllib.parse import urlencode

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from peachjam.models import Court, Judge, Locality
from peachjam_search.entity_matcher import EntityMatcher


class EntityMatcherTest(TestCase):
    fixtures = ["tests/countries", "tests/courts"]

    def setUp(self):
        cache.clear()

    def test_matches_court_name_exactly(self):
        hits = EntityMatcher().match("East African Court of Justice")

        self.assertEqual(1, len(hits))
        self.assertEqual("court", hits[0].entity_type)
        self.assertEqual("East African Court of Justice", hits[0].label)
        self.assertEqual("exact", hits[0].match_type)

    def test_matches_court_name_when_normalized(self):
        hits = EntityMatcher().match("east african court of justice")

        self.assertEqual(1, len(hits))
        self.assertEqual("court", hits[0].entity_type)
        self.assertEqual("normalized exact", hits[0].match_type)

    def test_matches_court_code(self):
        hits = EntityMatcher().match("eacj")

        self.assertEqual(1, len(hits))
        self.assertEqual("court", hits[0].entity_type)
        self.assertEqual(Court.objects.get(code="EACJ").pk, hits[0].entity_id)
        self.assertEqual("code exact", hits[0].match_type)

    def test_matches_locality_name_exactly(self):
        locality = Locality.objects.get(name="African Union (AU)")

        hits = EntityMatcher().match("African Union (AU)")

        self.assertEqual(1, len(hits))
        self.assertEqual("locality", hits[0].entity_type)
        self.assertEqual("African Union (AU)", hits[0].label)
        self.assertEqual("exact", hits[0].match_type)
        self.assertEqual(self.locality_legislation_url(locality), hits[0].url)

    def test_matches_locality_name_when_normalized(self):
        hits = EntityMatcher().match("african union au")

        self.assertEqual(1, len(hits))
        self.assertEqual("locality", hits[0].entity_type)
        self.assertEqual("normalized exact", hits[0].match_type)

    def test_matches_locality_name_without_parenthetical_suffix(self):
        hits = EntityMatcher().match("African Union")

        self.assertEqual(1, len(hits))
        self.assertEqual("locality", hits[0].entity_type)
        self.assertEqual("African Union (AU)", hits[0].label)
        self.assertEqual("normalized exact", hits[0].match_type)

    def test_matches_locality_place_code(self):
        hits = EntityMatcher().match("aa-au")

        self.assertEqual(1, len(hits))
        self.assertEqual("locality", hits[0].entity_type)
        self.assertEqual("place code exact", hits[0].match_type)

    @override_settings(ROOT_URLCONF="peachjam.urls.i18n")
    def test_matches_locality_without_locality_legislation_url(self):
        hits = EntityMatcher().match("African Union")

        self.assertEqual(1, len(hits))
        self.assertEqual(
            f"{reverse('legislation_list')}?{urlencode({'localities': 'African Union (AU)'})}",
            hits[0].url,
        )

    def test_matches_judge_name_exactly(self):
        Judge.objects.create(name="Mwangi")

        hits = EntityMatcher().match("Mwangi")

        self.assertEqual(1, len(hits))
        self.assertEqual("judge", hits[0].entity_type)
        self.assertEqual("Mwangi", hits[0].label)
        self.assertEqual("exact", hits[0].match_type)

    def test_matches_unique_judge_token(self):
        Judge.objects.create(name="Justice Jane Mwangi")

        hits = EntityMatcher().match("mwangi")

        self.assertEqual(1, len(hits))
        self.assertEqual("judge", hits[0].entity_type)
        self.assertEqual("Justice Jane Mwangi", hits[0].label)
        self.assertEqual("unique token", hits[0].match_type)

    def test_ignores_ambiguous_judge_token(self):
        Judge.objects.create(name="Justice Jane Mwangi")
        Judge.objects.create(name="Justice John Mwangi")

        hits = EntityMatcher().match("mwangi")

        self.assertEqual([], hits)

    def test_ignores_weak_court_partial_match(self):
        hits = EntityMatcher().match("african")

        self.assertEqual([], hits)

    def test_ignores_long_queries_before_checking_providers(self):
        class Provider:
            called = False

            def match(self, query, normalized_query):
                self.called = True
                return []

        provider = Provider()

        hits = EntityMatcher(providers=[provider]).match("x" * 51)

        self.assertEqual([], hits)
        self.assertFalse(provider.called)

    def locality_legislation_url(self, locality):
        try:
            return reverse(
                "locality_legislation_list", kwargs={"code": locality.place_code()}
            )
        except NoReverseMatch:
            return f"{reverse('legislation_list')}?{urlencode({'localities': locality.name})}"
