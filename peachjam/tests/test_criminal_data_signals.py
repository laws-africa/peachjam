from background_task.models import Task
from django.test import TestCase
from django.utils import timezone

from peachjam.models import Judgment, pj_settings


class CriminalDataSignalTests(TestCase):
    fixtures = [
        "tests/countries",
        "documents/sample_documents",
    ]

    def setUp(self):
        self.settings = pj_settings()
        self.settings.allow_criminal_data_extraction = True
        self.settings.save()
        self.judgment = Judgment.objects.first()
        self.judgment.get_or_create_document_content().update_text_content()
        Task.objects.all().delete()

    def test_changed_judgment_content_schedules_extraction(self):
        document_content = self.judgment.document_content
        document_content.content_text = f"{document_content.content_text}\nUpdated text"

        before = timezone.now()
        with self.captureOnCommitCallbacks(execute=True):
            document_content.save()

        task = Task.objects.filter(task_name__contains="extract_criminal_data").first()
        self.assertIn(str(self.judgment.pk), task.task_params)
        self.assertGreaterEqual(
            task.run_at,
            before + timezone.timedelta(minutes=59),
        )

    def test_unchanged_judgment_content_does_not_schedule_extraction(self):
        document_content = self.judgment.document_content

        with self.captureOnCommitCallbacks(execute=True):
            document_content.save()

        self.assertFalse(
            Task.objects.filter(task_name__contains="extract_criminal_data").exists()
        )
