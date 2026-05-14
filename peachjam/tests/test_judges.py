import datetime
from io import StringIO

from countries_plus.models import Country
from django.core.management import call_command
from django.test import TestCase
from languages_plus.models import Language

from peachjam.models import Bench, Court, Judge, JudgeAlias, JudgePerson, Judgment


class JudgeAliasModelTests(TestCase):
    def test_save_sets_normalized_name(self):
        judge_person = JudgePerson.objects.create(full_name="Abban", slug="abban")

        alias = JudgeAlias.objects.create(
            judge_person=judge_person,
            name=" ABBAN, J.A. ",
        )

        self.assertEqual("abban ja", alias.normalized_name)


class BackfillJudgePeopleCommandTests(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.legacy_judge_one = Judge.objects.create(name="Abban JA")
        self.legacy_judge_two = Judge.objects.create(name="ABBAN, J.A.")
        self.legacy_judge_three = Judge.objects.create(name="Abban, J")
        self.judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2024, 1, 3),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Abban v Republic",
        )
        self.bench_one = Bench.objects.create(
            judgment=self.judgment,
            judge=self.legacy_judge_one,
        )
        self.bench_two = Bench.objects.create(
            judgment=self.judgment,
            judge=self.legacy_judge_two,
        )
        self.bench_three = Bench.objects.create(
            judgment=self.judgment,
            judge=self.legacy_judge_three,
            title="Manual title",
            extracted_name="Manual extracted",
            is_manual_override=True,
        )

    def test_command_backfills_legacy_judges_into_new_tables(self):
        call_command("backfill_judge_people")

        alias_one = JudgeAlias.objects.get(name="Abban JA")
        alias_two = JudgeAlias.objects.get(name="ABBAN, J.A.")
        alias_three = JudgeAlias.objects.get(name="Abban, J")

        self.assertEqual(1, JudgePerson.objects.count())
        self.assertEqual(3, JudgeAlias.objects.count())
        self.assertEqual(alias_one.judge_person_id, alias_two.judge_person_id)
        self.assertEqual(alias_one.judge_person_id, alias_three.judge_person_id)
        self.assertEqual("abban", alias_one.judge_person.full_name.casefold())

        self.bench_one.refresh_from_db()
        self.bench_two.refresh_from_db()
        self.bench_three.refresh_from_db()

        self.assertEqual(alias_one.judge_person_id, self.bench_one.judge_person_id)
        self.assertEqual(alias_one.pk, self.bench_one.matched_alias_id)
        self.assertEqual("Abban JA", self.bench_one.extracted_name)
        self.assertEqual("JA", self.bench_one.title)

        self.assertEqual(alias_one.judge_person_id, self.bench_two.judge_person_id)
        self.assertEqual(alias_two.pk, self.bench_two.matched_alias_id)
        self.assertEqual("ABBAN, J.A.", self.bench_two.extracted_name)
        self.assertEqual("JA", self.bench_two.title)

        self.assertEqual(alias_three.judge_person_id, self.bench_three.judge_person_id)
        self.assertEqual(alias_three.pk, self.bench_three.matched_alias_id)
        self.assertEqual("Manual extracted", self.bench_three.extracted_name)
        self.assertEqual("Manual title", self.bench_three.title)

    def test_command_is_safe_to_run_twice(self):
        call_command("backfill_judge_people")
        call_command("backfill_judge_people")

        self.assertEqual(1, JudgePerson.objects.count())
        self.assertEqual(3, JudgeAlias.objects.count())

    def test_dry_run_shows_canonical_person_and_alias_mappings(self):
        out = StringIO()

        call_command("backfill_judge_people", "--dry-run", stdout=out)

        output = out.getvalue()

        self.assertIn("JudgePerson(full_name='Abban')", output)
        self.assertIn("JudgeAlias(name='Abban JA', normalized_name='abban ja')", output)
        self.assertIn(
            "JudgeAlias(name='ABBAN, J.A.', normalized_name='abban ja')", output
        )
        self.assertIn("JudgeAlias(name='Abban, J', normalized_name='abban j')", output)
