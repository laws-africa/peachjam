# Generated by Django 4.2.14 on 2024-11-07 06:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam_search", "0006_searchclick_score_searchtrace_filters_string"),
    ]

    operations = [
        migrations.AddField(
            model_name="searchtrace",
            name="suggestion",
            field=models.CharField(max_length=20, null=True),
        ),
    ]