from django.db import migrations
from django.db.models import F, Q

TRANSLATED_FIELDS = {
    "AttachedFileNature": ("name",),
    "Court": ("name",),
    "CourtClass": ("name",),
    "CourtRegistry": ("name",),
    "CustomPropertyLabel": ("name",),
    "DocumentNature": ("name",),
    "Label": ("name",),
    "Locality": ("name",),
    "Outcome": ("name",),
    "Predicate": ("verb", "reverse_verb"),
    "Taxonomy": ("name", "path_name"),
    "Treatment": ("name",),
}


def backfill_english_translations(apps, schema_editor):
    for model_name, field_names in TRANSLATED_FIELDS.items():
        model = apps.get_model("peachjam", model_name)
        for field_name in field_names:
            translated_field = f"{field_name}_en"
            model.objects.filter(
                Q(**{f"{translated_field}__isnull": True}) | Q(**{translated_field: ""})
            ).update(**{translated_field: F(field_name)})


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0323_backfill_locality_name_en"),
    ]

    operations = [
        migrations.RunPython(
            backfill_english_translations,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
