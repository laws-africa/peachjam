# Generated by Django 3.2.20 on 2023-11-20 10:34

import martor.models
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0112_peachjamsettings_pagerank_pivot_value"),
    ]

    operations = [
        migrations.AddField(
            model_name="book",
            name="content_markdown",
            field=martor.models.MartorField(blank=True, null=True),
        ),
    ]
