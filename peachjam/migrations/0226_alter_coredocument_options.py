# Generated by Django 4.2 on 2025-06-09 13:24

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0225_judgment_blurb_judgment_held_judgment_issues_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="coredocument",
            options={
                "ordering": ["doc_type", "title"],
                "permissions": [
                    ("can_delete_own_document", "Can delete own document"),
                    ("can_edit_own_document", "Can edit own document"),
                    ("can_edit_advanced_fields", "Can edit advanced fields"),
                    ("can_debug_document", "Can do document debugging"),
                    ("can_view_document_summary", "Can view document summary"),
                    ("can_generate_judgment_summary", "Can generate judgment summary"),
                ],
            },
        ),
    ]
