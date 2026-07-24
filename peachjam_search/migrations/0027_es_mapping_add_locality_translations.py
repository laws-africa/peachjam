import os

from django.db import migrations


def forwards(apps, schema_editor):
    from django.conf import settings
    from django_elasticsearch_dsl.registries import registry

    if not settings.DEBUG and os.environ.get("ELASTICSEARCH_HOST"):
        for ix in registry.get_indices():
            if not ix._mapping:
                continue
            print(f"Adding translated locality field mappings for {ix._name}")

            fields = """
            locality_en
            locality_fr
            locality_pt
            locality_sw
            """.split()
            body = {
                "dynamic": "strict",
                "properties": {
                    **{field: ix._mapping[field].to_dict() for field in fields}
                },
            }
            ix.connection.indices.put_mapping(
                index=ix._name,
                body=body,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0310_locality_name_translations"),
        ("peachjam_search", "0026_es_mapping_add_gazette_publication_fields"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
