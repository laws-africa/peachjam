from django.db import migrations
from django.db.models import Q


def queue_anonymised_source_file_pdfs(apps, schema_editor):
    """Regenerate derived PDFs so their object names use the anonymised case name."""
    from peachjam.tasks import create_anonymised_source_file_pdf

    Judgment = apps.get_model("peachjam", "Judgment")
    judgments = (
        Judgment.objects.filter(
            anonymised=True,
            document_content__content_html__isnull=False,
        )
        .exclude(document_content__content_html="")
        .filter(Q(source_file__isnull=True) | Q(source_file__file_is_anonymised=False))
    )

    for judgment_id in judgments.values_list("pk", flat=True).iterator():
        # Queue rather than render in the migration: PDF generation is expensive and the task re-checks the
        # anonymisation state and derived-file inputs before saving.
        create_anonymised_source_file_pdf(judgment_id, schedule=60)


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0316_finalize_judge_identity_fields"),
    ]

    operations = [
        migrations.RunPython(
            queue_anonymised_source_file_pdfs,
            migrations.RunPython.noop,
        ),
    ]
