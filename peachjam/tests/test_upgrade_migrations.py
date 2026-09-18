from importlib import import_module
from types import SimpleNamespace

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase


class MigrationTestCase(TransactionTestCase):
    migrate_from = None
    migrate_to = None

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        self.leaf_nodes = executor.loader.graph.leaf_nodes()
        executor.migrate([self.migrate_from])
        self.old_apps = executor.loader.project_state([self.migrate_from]).apps

    def migrate(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        return executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.leaf_nodes)
        super().tearDown()


class RelationshipTargetMigrationTests(TransactionTestCase):
    def test_deduplicates_null_targets_before_making_them_non_null(self):
        migration = import_module(
            "peachjam.migrations.0210_alter_relationship_object_target_id_and_more"
        )
        table = "test_relationship_target_migration"
        with connection.cursor() as cursor:
            cursor.execute(f"""
                CREATE TABLE {table} (
                    id bigint PRIMARY KEY,
                    subject_work_id bigint NOT NULL,
                    subject_target_id varchar(1024),
                    object_work_id bigint NOT NULL,
                    object_target_id varchar(1024),
                    predicate_id bigint NOT NULL
                )
                """)
            cursor.execute(f"""
                INSERT INTO {table} VALUES
                    (1, 10, NULL, 20, NULL, 30),
                    (2, 10, NULL, 20, NULL, 30),
                    (3, 10, '', 20, '', 30),
                    (4, 10, NULL, 20, 'section-1', 30)
                """)

        relationship = SimpleNamespace(
            _meta=SimpleNamespace(db_table=table),
        )
        apps = SimpleNamespace(get_model=lambda *args: relationship)
        try:
            with connection.schema_editor() as schema_editor:
                migration.remove_duplicate_relationships(apps, schema_editor)
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT id FROM {table} ORDER BY id")
                self.assertEqual([(1,), (4,)], cursor.fetchall())
        finally:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")


class LimitTaxonomiesMigrationTests(SimpleTestCase):
    def test_identifies_only_redundant_ancestor_topics(self):
        migration = import_module("peachjam.migrations.0223_limit_taxonomies")
        parent = SimpleNamespace(pk=1, path="0001", depth=1)
        child = SimpleNamespace(pk=2, path="00010001", depth=2)
        unrelated = SimpleNamespace(pk=3, path="0002", depth=1)
        links = [
            SimpleNamespace(topic_id=1, topic=parent),
            SimpleNamespace(topic_id=2, topic=child),
            SimpleNamespace(topic_id=3, topic=unrelated),
        ]

        self.assertEqual([1], migration.redundant_topic_ids(links))


class LocalityNameMigrationTests(MigrationTestCase):
    migrate_from = ("peachjam", "0322_alter_email_alert_frequency_choices")
    migrate_to = ("peachjam", "0323_backfill_locality_name_en")

    def test_backfills_only_missing_english_names(self):
        Country = self.old_apps.get_model("countries_plus", "Country")
        Locality = self.old_apps.get_model("peachjam", "Locality")
        country = Country.objects.create(
            iso="KE", iso3="KEN", iso_numeric=404, name="Kenya"
        )
        blank = Locality.objects.create(
            name="Nairobi", name_en="", jurisdiction=country, code="nairobi"
        )
        translated = Locality.objects.create(
            name="Mombasa",
            name_en="Mombasa County",
            jurisdiction=country,
            code="mombasa",
        )

        apps = self.migrate()
        Locality = apps.get_model("peachjam", "Locality")

        self.assertEqual("Nairobi", Locality.objects.get(pk=blank.pk).name_en)
        self.assertEqual(
            "Mombasa County", Locality.objects.get(pk=translated.pk).name_en
        )
