from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class JudgePersonNameMigrationTests(TransactionTestCase):
    migrate_from = ("peachjam", "0313_mark_external_citation_links_manual")
    migrate_to = ("peachjam", "0315_judgetitle")

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        self.leaf_nodes = executor.loader.graph.leaf_nodes()
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        JudgePerson = old_apps.get_model("peachjam", "JudgePerson")
        JudgeAlias = old_apps.get_model("peachjam", "JudgeAlias")

        JudgePerson.objects.create(
            full_name="Savage, Katherine",
            slug="savage-katherine",
        )
        JudgePerson.objects.create(
            full_name="Dennis M Mwangi",
            slug="dennis-m-mwangi",
        )
        duplicate = JudgePerson.objects.create(
            full_name="Katherine Savage",
            slug="katherine-savage",
        )
        JudgeAlias.objects.create(
            judge_person=duplicate,
            name="Savage JA",
            normalized_name="savage ja",
            title="JA",
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.leaf_nodes)
        super().tearDown()

    def test_splits_names_merges_duplicates_and_links_titles(self):
        JudgePerson = self.apps.get_model("peachjam", "JudgePerson")
        JudgeAlias = self.apps.get_model("peachjam", "JudgeAlias")

        savage = JudgePerson.objects.get(last_name="Savage")
        mwangi = JudgePerson.objects.get(last_name="M Mwangi")
        alias = JudgeAlias.objects.select_related("title").get(name="Savage JA")

        self.assertEqual("Katherine", savage.first_name)
        self.assertEqual("Dennis", mwangi.first_name)
        self.assertEqual(savage.pk, alias.judge_person_id)
        self.assertEqual("Judge of appeal", alias.title.name)
        self.assertEqual("JA", alias.title.abbreviation)

    def test_restores_full_names_when_reversed(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        JudgePerson = old_apps.get_model("peachjam", "JudgePerson")

        self.assertTrue(
            JudgePerson.objects.filter(full_name="Katherine Savage").exists()
        )
        self.assertTrue(
            JudgePerson.objects.filter(full_name="Dennis M Mwangi").exists()
        )
