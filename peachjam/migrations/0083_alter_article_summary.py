# Generated by Django 3.2.16 on 2023-05-24 15:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0082_peachjamsettings_metabase_dashboard_link"),
    ]

    operations = [
        migrations.AlterField(
            model_name="article",
            name="summary",
            field=models.TextField(blank=True, null=True, verbose_name="summary"),
        ),
    ]