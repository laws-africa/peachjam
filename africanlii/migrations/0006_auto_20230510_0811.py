# Generated by Django 3.2.18 on 2023-05-10 08:11

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("countries_plus", "0005_auto_20160224_1804"),
        ("peachjam", "0072_backfill_created_by"),
        ("africanlii", "0005_ratification"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="ratificationcountry",
            options={
                "ordering": ["country__name"],
                "verbose_name": "ratification country",
                "verbose_name_plural": "ratification countries",
            },
        ),
        migrations.CreateModel(
            name="RegionalEconomicCommunity",
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
                    "locality",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="peachjam.locality",
                        verbose_name="locality",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Regional economic communities",
            },
        ),
        migrations.CreateModel(
            name="MemberState",
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
                    "country",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="countries_plus.country",
                        verbose_name="country",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="AfricanUnionOrgan",
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
                    "author",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="peachjam.author",
                        verbose_name="author",
                    ),
                ),
            ],
        ),
    ]