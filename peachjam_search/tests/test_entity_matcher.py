from django.test import TestCase

from peachjam.models import Court, Judge
from peachjam_search.entity_matcher import EntityMatcher


class EntityMatcherTest(TestCase):
    fixtures = ["tests/countries", "tests/courts"]

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
