# Generated by Django 4.2.14 on 2024-11-22 09:06

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0183_article_featured"),
    ]

    operations = [
        migrations.AddField(
            model_name="bill",
            name="author",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="peachjam.author",
                verbose_name="author",
            ),
        ),
    ]
