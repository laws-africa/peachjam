from django.db import migrations


def reverse_backfill_document_content(apps, schema_editor):
    pass


def backfill_document_content(apps, schema_editor):
    conn = schema_editor.connection

    with conn.cursor() as cursor:
        cursor.execute("LOCK TABLE peachjam_documentcontent IN ACCESS EXCLUSIVE MODE")
        cursor.execute("""
            INSERT INTO peachjam_documentcontent (
                document_id,
                content_html,
                source_html,
                content_html_is_akn,
                toc_json
            )
            SELECT
                d.id,
                d.content_html,
                d.content_html,
                COALESCE(d.content_html_is_akn, FALSE),
                d.toc_json
            FROM peachjam_coredocument d
            ON CONFLICT (document_id) DO UPDATE
            SET
                content_html = EXCLUDED.content_html,
                source_html = EXCLUDED.source_html,
                content_html_is_akn = EXCLUDED.content_html_is_akn,
                toc_json = EXCLUDED.toc_json
            """)


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0282_add_coredocument_content_html_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_document_content, reverse_backfill_document_content
        ),
    ]
