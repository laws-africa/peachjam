from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0328_legalsubject_leadingauthority_and_more"),
    ]

    operations = [
        # Raw SQL preserves the stored s3:bucket:key values and bypasses file hooks.
        # Restoring previous source URLs requires a data backup; rollback is a no-op.
        migrations.RunSQL(
            sql=r"""
                UPDATE peachjam_sourcefile AS source
                SET source_url = NULL
                FROM peachjam_gazette AS gazette
                WHERE source.document_id = gazette.coredocument_ptr_id
                  AND source.source_url ~* '^https?://(www\.)?(archive\.)?gazettes\.africa(:[0-9]+)?([/?#]|$)'
                  AND source.file LIKE 's3:lawsafrica-gazettes-archive:%'
                  AND source.file <> 's3:lawsafrica-gazettes-archive:'
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
