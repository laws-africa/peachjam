# Generated by Django 3.2.13 on 2022-07-13 12:36

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("countries_plus", "0005_auto_20160224_1804"),
        ("languages_plus", "0004_auto_20171214_0004"),
        ("peachjam", "0007_file_cascade_delete"),
    ]

    operations = [
        migrations.CreateModel(
            name="PeachJamSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "default_document_language",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="languages_plus.language",
                    ),
                ),
                (
                    "document_jurisdictions",
                    models.ManyToManyField(
                        related_name="_peachjam_peachjamsettings_document_jurisdictions_+",
                        to="countries_plus.Country",
                    ),
                ),
                (
                    "document_languages",
                    models.ManyToManyField(
                        related_name="_peachjam_peachjamsettings_document_languages_+",
                        to="languages_plus.Language",
                    ),
                ),
            ],
            options={
                "verbose_name": "site settings",
                "verbose_name_plural": "site settings",
            },
        ),
    ]
