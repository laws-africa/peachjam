# Generated by Django 4.2.15 on 2024-11-19 16:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam_search", "0009_savedsearch"),
    ]

    operations = [
        migrations.AlterField(
            model_name="savedsearch",
            name="filters",
            field=models.CharField(blank=True, max_length=4098, null=True),
        ),
    ]