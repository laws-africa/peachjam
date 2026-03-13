from django.db import connection, models
from django.test import TransactionTestCase
from django.test.utils import isolate_apps
from django_lifecycle import AFTER_SAVE, BEFORE_SAVE

from peachjam.models.lifecycle import (
    AttributeHooksMixin,
    attribute_dag,
    on_attribute_changed,
)


@isolate_apps("peachjam")
class OnAttributeChangedTestCase(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        attribute_dag.clear()
        cls.before_save_calls = []
        cls.after_save_calls = []
        cls.after_save_calls_2 = []

        class OnClassHookModel(AttributeHooksMixin, models.Model):
            source = models.CharField(max_length=50, null=True, blank=True)
            derived = models.CharField(max_length=50, null=True, blank=True)

            class Meta:
                app_label = "peachjam"

            @on_attribute_changed(BEFORE_SAVE, ["source"], ["derived"])
            def derive_value(self):
                type(self)._before_save_calls.append(self.source)
                self.derived = f"derived:{self.source}"

        class OffClassHookModel(AttributeHooksMixin, models.Model):
            source = models.CharField(max_length=50, null=True, blank=True)

            class Meta:
                app_label = "peachjam"

        cls.OnClassHookModel = OnClassHookModel
        cls.OffClassHookModel = OffClassHookModel
        cls.OnClassHookModel._before_save_calls = cls.before_save_calls

        @on_attribute_changed(
            cls.OffClassHookModel,
            AFTER_SAVE,
            ["source"],
            ["CoreDocument.citations"],
        )
        def record_source_change(instance):
            cls.after_save_calls.append(instance.source)

        @on_attribute_changed(
            cls.OffClassHookModel,
            AFTER_SAVE,
            ["source"],
            ["CoreDocument.citations"],
        )
        def record_source_change_again(instance):
            cls.after_save_calls_2.append(instance.source)

        cls.record_source_change = record_source_change
        cls.record_source_change_again = record_source_change_again

        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(cls.OnClassHookModel)
            schema_editor.create_model(cls.OffClassHookModel)

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(cls.OffClassHookModel)
            schema_editor.delete_model(cls.OnClassHookModel)
        attribute_dag.clear()
        super().tearDownClass()

    def setUp(self):
        self.before_save_calls.clear()
        self.after_save_calls.clear()
        self.after_save_calls_2.clear()

    def test_on_class_hook_runs_before_save_when_tracked_attribute_changes(self):
        obj = self.OnClassHookModel.objects.create(source="initial")
        obj.track_changes()
        obj.source = "updated"
        obj.save()
        obj.refresh_from_db()

        self.assertEqual(["updated"], self.before_save_calls)
        self.assertEqual("derived:updated", obj.derived)

    def test_off_class_hook_runs_after_save_when_tracked_attribute_changes(self):
        obj = self.OffClassHookModel.objects.create(source="initial")
        obj.track_changes()
        obj.source = "updated"
        obj.save()

        self.assertEqual(["updated"], self.after_save_calls)
        self.assertEqual(["updated"], self.after_save_calls_2)

    def test_attribute_dag_records_fully_qualified_edges(self):
        edges = attribute_dag.edges()

        self.assertIn(
            ("OnClassHookModel.source", "OnClassHookModel.derived"),
            edges,
        )
        self.assertIn(
            ("OffClassHookModel.source", "CoreDocument.citations"),
            edges,
        )

        on_class_metadata = edges[
            ("OnClassHookModel.source", "OnClassHookModel.derived")
        ][0]
        self.assertEqual("on-class", on_class_metadata.declaration_mode)
        self.assertEqual(BEFORE_SAVE, on_class_metadata.timing)

    def test_attribute_dag_deduplicates_edges_and_accumulates_metadata(self):
        edges = attribute_dag.edges()
        metadata = edges[("OffClassHookModel.source", "CoreDocument.citations")]

        self.assertEqual(2, len(metadata))
        self.assertEqual(
            {"record_source_change", "record_source_change_again"},
            {item.function_name for item in metadata},
        )
