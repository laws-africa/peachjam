# Generated by Django 4.2.15 on 2024-09-11 09:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0155_entityprofile_title"),
    ]

    operations = [
        migrations.RenameField(
            model_name="legislation",
            old_name="metadata_json",
            new_name="old_metadata_json",
        ),
        migrations.AddField(
            model_name="coredocument",
            name="metadata_json",
            field=models.JSONField(blank=True, null=True, verbose_name="metadata JSON"),
        ),
        migrations.AddField(
            model_name="legislation",
            name="principal",
            field=models.BooleanField(default=False, verbose_name="principal"),
        ),
    ]
