# Generated by Django 4.2.14 on 2024-10-28 11:00

from django.db import migrations


def migrate_settings(apps, schema_editor):
    Ingestor = apps.get_model("peachjam", "Ingestor")
    IngestorSetting = apps.get_model("peachjam", "IngestorSetting")

    for ingestor in Ingestor.objects.filter(adapter="IndigoAdapter"):
        # ensure we exclude bills
        setting, _ = IngestorSetting.objects.get_or_create(
            ingestor=ingestor, name="exclude_doctypes"
        )
        setting.value = ((setting.value or "") + " bill").strip()
        setting.save()

        # rename actor to include_actors
        IngestorSetting.objects.filter(ingestor=ingestor, name="actor").update(
            name="include_actors"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0170_ratification_updated_at_alter_ratification_table_and_more"),
    ]

    operations = [
        migrations.RunPython(migrate_settings, migrations.RunPython.noop),
    ]
