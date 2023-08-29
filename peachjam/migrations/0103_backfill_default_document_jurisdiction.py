# Generated by Django 3.2.19 on 2023-08-29 09:40

from django.db import migrations


def backfill_default_document_jurisdiction(apps, schema_editor):
    site_settings_model = apps.get_model("peachjam", "PeachJamSettings")
    site_settings = site_settings_model.objects.filter(pk=1).first()
    if site_settings:
        site_settings.default_document_jurisdiction = (
            site_settings.document_jurisdictions.first()
        )
        site_settings.save()


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0102_change_judgment_admin_labels"),
    ]

    operations = [
        migrations.RunPython(
            backfill_default_document_jurisdiction, migrations.RunPython.noop
        ),
    ]