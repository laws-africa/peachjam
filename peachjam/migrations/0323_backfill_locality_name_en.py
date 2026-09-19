from django.db import migrations
from django.db.models import F, Q


def backfill_locality_name_en(apps, schema_editor):
    Locality = apps.get_model("peachjam", "Locality")
    Locality.objects.filter(Q(name_en__isnull=True) | Q(name_en="")).update(
        name_en=F("name")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0322_alter_email_alert_frequency_choices"),
    ]

    operations = [
        migrations.RunPython(
            backfill_locality_name_en,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
