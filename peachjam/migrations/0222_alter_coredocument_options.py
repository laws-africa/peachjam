# Generated by Django 4.2.14 on 2025-05-21 07:51

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0221_alter_saveddocument_unique_together_and_more"),
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
                ],
            },
        ),
    ]
