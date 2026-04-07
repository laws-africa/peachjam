from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0289_normalize_criminal_tag_models"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="judgmentoffence",
            name="case_tags",
        ),
        migrations.RemoveField(
            model_name="offence",
            name="offence_tags",
        ),
        migrations.RemoveField(
            model_name="offencecategory",
            name="is_active",
        ),
        migrations.RemoveField(
            model_name="offencecategory",
            name="order",
        ),
    ]
