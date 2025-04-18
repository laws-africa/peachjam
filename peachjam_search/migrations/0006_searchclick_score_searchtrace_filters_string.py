# Generated by Django 4.2.14 on 2024-10-31 16:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam_search", "0005_es_mapping_add_judges_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="searchclick",
            name="score",
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name="searchtrace",
            name="filters_string",
            field=models.CharField(max_length=2048, null=True),
        ),
        migrations.RunSQL(
            """
        UPDATE peachjam_search_searchclick SET score = EXP(-0.1733 * (position - 1)) WHERE score is NULL;
        UPDATE peachjam_search_searchtrace SET filters = filters - 'is_most_recent' WHERE filters ? 'is_most_recent';
        """,
            migrations.RunSQL.noop,
        ),
    ]
