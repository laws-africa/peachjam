import django.contrib.postgres.indexes
from django.db import migrations, models
from django.db.models.functions import Upper


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0324_backfill_english_translations"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="flynote",
            index=models.Index(
                django.contrib.postgres.indexes.OpClass(
                    Upper("name"), name="text_pattern_ops"
                ),
                condition=models.Q(deprecated=False),
                name="pj_flynote_name_prefix_idx",
            ),
        ),
    ]
