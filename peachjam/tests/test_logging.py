import logging

from django.test import SimpleTestCase

from peachjam.logging import LoggingContextFilter, log_context


class LoggingContextFilterTest(SimpleTestCase):
    def setUp(self):
        self.filter = LoggingContextFilter()

    def make_record(self, **kwargs):
        record = logging.makeLogRecord(kwargs)
        self.filter.filter(record)
        return record

    def test_uses_request_id_without_task_context(self):
        record = self.make_record(request_id="request-1")

        self.assertEqual("-", record.task_run_id)
        self.assertEqual("request-1", record.correlation_id)
        self.assertEqual("-", record.frbr_uri)

    def test_uses_task_run_id_as_correlation_id(self):
        with log_context(task_run_id="task-1"):
            record = self.make_record(request_id="request-1")

        self.assertEqual("task-1", record.task_run_id)
        self.assertEqual("task-1", record.correlation_id)

    def test_restores_nested_contexts(self):
        with log_context(task_run_id="outer"):
            with log_context(task_run_id="inner"):
                self.assertEqual("inner", self.make_record().task_run_id)

            self.assertEqual("outer", self.make_record().task_run_id)

        self.assertEqual("-", self.make_record().task_run_id)

    def test_none_values_do_not_replace_existing_context(self):
        with log_context(task_run_id="task-1", frbr_uri="/akn/za/judgment/1"):
            with log_context(frbr_uri=None):
                record = self.make_record()

        self.assertEqual("task-1", record.task_run_id)
        self.assertEqual("/akn/za/judgment/1", record.frbr_uri)

    def test_context_is_additive(self):
        with log_context(task_run_id="task-1"):
            with log_context(frbr_uri="/akn/za/judgment/1"):
                record = self.make_record()

        self.assertEqual("task-1", record.task_run_id)
        self.assertEqual("/akn/za/judgment/1", record.frbr_uri)

    def test_log_context_can_be_used_as_a_decorator(self):
        @log_context(task_run_id="decorated")
        def get_task_run_id():
            return self.make_record().task_run_id

        self.assertEqual("decorated", get_task_run_id())
        self.assertEqual("-", self.make_record().task_run_id)

    def test_log_context_rejects_unknown_context_keys(self):
        with self.assertRaises(TypeError):
            log_context(task_id="task-1")
