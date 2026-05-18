import datetime
from io import StringIO

from countries_plus.models import Country
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from languages_plus.models import Language

from peachjam.analysis.judges import judge_identity_service
from peachjam.models import Bench, Court, Judge, JudgeAlias, JudgePerson, Judgment


class JudgeParsingTests(TestCase):
    def test_parse_judge_name_splits_source_name_and_title(self):
        parts = judge_identity_service.parse_judge_name(" ABBAN, J.A. ")

        self.assertEqual("ABBAN, J.A.", parts["raw_name"])
        self.assertEqual("abban ja", parts["normalized_name"])
        self.assertEqual("abban", parts["base_name"])
        self.assertEqual("JA", parts["title"])


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

    def test_command_reuses_existing_case_insensitive_judge_person(self):
        existing = JudgePerson.objects.create(
            full_name="ABBAN",
            slug="abban-existing",
        )

        call_command("backfill_judge_people")

        self.assertEqual(1, JudgePerson.objects.count())
        self.assertEqual(existing.pk, JudgePerson.objects.get().pk)

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


class JudgeIdentityWorkflowAdminTests(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="judge-admin@example.com",
            email="judge-admin@example.com",
            password="password",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.admin_user)
        self.workflow_url = reverse("peachjam_judgeperson_workflow")
        self.target = JudgePerson.objects.create(full_name="Abban", slug="abban")
        self.duplicate = JudgePerson.objects.create(
            full_name="Abban duplicate",
            slug="abban-duplicate",
        )
        self.empty_judge_person = JudgePerson.objects.create(
            full_name="Unused judge person",
            slug="unused-judge-person",
        )
        self.alias_one = JudgeAlias.objects.create(
            judge_person=self.duplicate,
            name="Abban JA",
        )
        self.alias_two = JudgeAlias.objects.create(
            judge_person=self.duplicate,
            name="ABBAN, J.A.",
        )
        self.legacy_judge_one = Judge.objects.create(name="Abban JA")
        self.legacy_judge_two = Judge.objects.create(name="ABBAN, J.A.")
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
            judge_person=self.duplicate,
            matched_alias=self.alias_one,
            extracted_name="Abban JA",
            title="JA",
        )
        self.bench_two = Bench.objects.create(
            judgment=self.judgment,
            judge=self.legacy_judge_two,
            judge_person=self.duplicate,
            matched_alias=self.alias_two,
            title="Manual title",
            extracted_name="Manual extracted",
            is_manual_override=True,
        )

    def test_workflow_page_loads(self):
        response = self.client.get(self.workflow_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Judge identity workflow")
        self.assertContains(response, "Alias connections")
        self.assertContains(response, "Judge people")
        self.assertContains(response, "Abban JA")

    def test_workflow_relinks_legacy_judges_and_moves_alias_ownership(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "apply_identity_changes",
                "target_judge_person": str(self.target.pk),
                "target_full_name": "",
                "selected_aliases": [
                    str(self.alias_one.pk),
                    str(self.alias_two.pk),
                ],
                "q": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Moved 2 selected aliases")
        self.assertContains(response, "deleted 1 now-empty source judge people")
        self.assertFalse(JudgePerson.objects.filter(pk=self.duplicate.pk).exists())

        aliases = set(self.target.aliases.values_list("name", flat=True))
        self.assertEqual(aliases, {"Abban JA", "ABBAN, J.A."})

        self.bench_one.refresh_from_db()
        self.bench_two.refresh_from_db()

        alias_one = JudgeAlias.objects.get(
            judge_person=self.target,
            name="Abban JA",
        )
        alias_two = JudgeAlias.objects.get(
            judge_person=self.target,
            name="ABBAN, J.A.",
        )

        self.assertEqual(self.bench_one.judge_person_id, self.target.pk)
        self.assertEqual(self.bench_one.matched_alias_id, alias_one.pk)
        self.assertEqual(self.bench_one.extracted_name, "Abban JA")
        self.assertEqual(self.bench_one.title, "JA")

        self.assertEqual(self.bench_two.judge_person_id, self.target.pk)
        self.assertEqual(self.bench_two.matched_alias_id, alias_two.pk)
        self.assertEqual(self.bench_two.extracted_name, "Manual extracted")
        self.assertEqual(self.bench_two.title, "Manual title")

    def test_workflow_can_create_canonical_judge_from_selected_legacy_judges(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "apply_identity_changes",
                "target_judge_person": "",
                "target_full_name": "",
                "selected_aliases": [str(self.alias_two.pk)],
                "q": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(JudgePerson.objects.filter(full_name="ABBAN").exists())
        self.assertTrue(JudgePerson.objects.filter(pk=self.duplicate.pk).exists())

        created_person = JudgePerson.objects.get(full_name="ABBAN")
        alias = JudgeAlias.objects.get(
            judge_person=created_person,
            name="ABBAN, J.A.",
        )

        self.bench_two.refresh_from_db()
        self.assertEqual(self.bench_two.judge_person_id, created_person.pk)
        self.assertEqual(self.bench_two.matched_alias_id, alias.pk)

    def test_workflow_can_rename_selected_target_judge_person(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "apply_identity_changes",
                "target_judge_person": str(self.target.pk),
                "target_full_name": "Justice Abban",
                "q": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Renamed judge person")

        self.target.refresh_from_db()
        self.assertEqual(self.target.full_name, "Justice Abban")
        self.assertEqual(self.target.slug, "justice-abban")

    def test_workflow_can_move_aliases_and_rename_target_judge_person(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "apply_identity_changes",
                "target_judge_person": str(self.target.pk),
                "target_full_name": "Justice Abban",
                "selected_aliases": [
                    str(self.alias_one.pk),
                    str(self.alias_two.pk),
                ],
                "q": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Moved 2 selected aliases")
        self.assertContains(response, 'renamed the judge person from "Abban"')
        self.assertFalse(JudgePerson.objects.filter(pk=self.duplicate.pk).exists())

        self.target.refresh_from_db()
        self.assertEqual(self.target.full_name, "Justice Abban")

        aliases = set(self.target.aliases.values_list("name", flat=True))
        self.assertEqual(aliases, {"Abban JA", "ABBAN, J.A."})

    def test_workflow_can_merge_selected_judge_people(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "merge_judge_people",
                "selected_judge_people": [str(self.duplicate.pk)],
                "merge_target_judge_person": str(self.target.pk),
                "q": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Merged 1 selected judge people")
        self.assertFalse(JudgePerson.objects.filter(pk=self.duplicate.pk).exists())

        aliases = set(self.target.aliases.values_list("name", flat=True))
        self.assertEqual(aliases, {"Abban JA", "ABBAN, J.A."})

        self.bench_one.refresh_from_db()
        self.bench_two.refresh_from_db()
        self.assertEqual(self.bench_one.judge_person_id, self.target.pk)
        self.assertEqual(self.bench_two.judge_person_id, self.target.pk)

    def test_workflow_can_delete_selected_aliases_only(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "delete_records",
                "delete_mode": "aliases",
                "selected_aliases": [str(self.alias_two.pk)],
                "q": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deleted 1 aliases")
        self.assertTrue(JudgePerson.objects.filter(pk=self.duplicate.pk).exists())
        self.assertFalse(JudgeAlias.objects.filter(pk=self.alias_two.pk).exists())

        self.bench_two.refresh_from_db()
        self.assertEqual(self.bench_two.judge_person_id, self.duplicate.pk)
        self.assertIsNone(self.bench_two.matched_alias_id)

    def test_workflow_can_delete_selected_judge_people_only(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "delete_records",
                "delete_mode": "judge_people",
                "selected_judge_people": [str(self.duplicate.pk)],
                "q": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deleted 1 judge people")
        self.assertContains(response, "Deleted 2 aliases")
        self.assertContains(response, "Cleared 2 matched alias links")
        self.assertContains(response, "Cleared 2 judge person links")
        self.assertFalse(JudgePerson.objects.filter(pk=self.duplicate.pk).exists())
        self.assertFalse(JudgeAlias.objects.filter(pk=self.alias_one.pk).exists())
        self.assertFalse(JudgeAlias.objects.filter(pk=self.alias_two.pk).exists())

        self.bench_one.refresh_from_db()
        self.bench_two.refresh_from_db()
        self.assertIsNone(self.bench_one.judge_person_id)
        self.assertIsNone(self.bench_one.matched_alias_id)
        self.assertIsNone(self.bench_two.judge_person_id)
        self.assertIsNone(self.bench_two.matched_alias_id)

    def test_workflow_can_delete_aliases_and_judge_people_together(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "delete_records",
                "delete_mode": "both",
                "selected_aliases": [str(self.alias_one.pk)],
                "selected_judge_people": [str(self.empty_judge_person.pk)],
                "q": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deleted 1 aliases")
        self.assertContains(response, "Deleted 1 judge people")
        self.assertFalse(JudgeAlias.objects.filter(pk=self.alias_one.pk).exists())
        self.assertFalse(
            JudgePerson.objects.filter(pk=self.empty_judge_person.pk).exists()
        )

        self.bench_one.refresh_from_db()
        self.assertEqual(self.bench_one.judge_person_id, self.duplicate.pk)
        self.assertIsNone(self.bench_one.matched_alias_id)

    def test_workflow_requires_judge_people_selection_for_judge_delete(self):
        response = self.client.post(
            self.workflow_url,
            {
                "action": "delete_records",
                "delete_mode": "judge_people",
                "q": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Select at least one judge person to delete.",
        )
        self.assertTrue(JudgePerson.objects.filter(pk=self.duplicate.pk).exists())
