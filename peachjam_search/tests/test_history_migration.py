from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class HistoryMigrationTests(TransactionTestCase):
    migrate_from = ("peachjam_search", "0033_searchhistory_and_more")
    migrate_to = ("peachjam_search", "0034_searchtrace_hidden_delete_searchhistory")

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        self.apps = executor.loader.project_state([self.migrate_from]).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate([self.migrate_to])
        super().tearDown()

    def test_removals_survive_without_hiding_other_users_or_later_searches(self):
        User = self.apps.get_model("auth", "User")
        Trace = self.apps.get_model("peachjam_search", "SearchTrace")
        History = self.apps.get_model("peachjam_search", "SearchHistory")
        user = User.objects.create(username="history-user")
        other = User.objects.create(username="other-user")

        def trace(**kwargs):
            return Trace.objects.create(
                **{
                    "user": user,
                    "search": "Law",
                    "page": 1,
                    "config_version": "test",
                    "n_results": 1,
                    **kwargs,
                }
            )

        hidden = [
            trace(),
            trace(search=" law ", filters={}, field_searches={}, ordering="-score"),
            trace(search="\tLAW\n"),
            trace(search="Case   law"),
        ]
        visible = [
            trace(user=other),
            trace(search="contract"),
            trace(filters={"court": ["high-court"]}),
            trace(field_searches={"title": "law"}),
            trace(mode="hybrid"),
            trace(ordering="-date"),
            trace(page=2),
        ]
        History.objects.create(
            user=user,
            key="removed",
            text="Law",
            query_string="q=LAW&page=1&ordering=-score&mode=text&gsc.tab=0",
            removed=True,
        )
        History.objects.create(
            user=user,
            key="spacing-removal",
            text="Case law",
            query_string="q=case+law",
            removed=True,
        )
        History.objects.create(
            user=user,
            key="filtered-removal",
            text="contract",
            query_string="q=contract&court=high-court",
            removed=True,
        )
        History.objects.create(
            user=user, key="visible", text="kept", query_string="q=kept", removed=False
        )
        visible.extend([trace(search="kept"), trace()])

        MigrationExecutor(connection).migrate([self.migrate_to])
        apps = (
            MigrationExecutor(connection).loader.project_state([self.migrate_to]).apps
        )
        Trace = apps.get_model("peachjam_search", "SearchTrace")
        self.assertEqual(
            set(Trace.objects.filter(hidden=True).values_list("pk", flat=True)),
            {t.pk for t in hidden},
        )
        self.assertFalse(
            Trace.objects.filter(pk__in=[t.pk for t in visible], hidden=True).exists()
        )
        self.assertEqual(Trace.objects.count(), len(hidden) + len(visible))
