import os

from django.db import migrations


def forwards(apps, schema_editor):
    from django.conf import settings
    from django_elasticsearch_dsl.registries import registry

    if not settings.DEBUG and os.environ.get("ELASTICSEARCH_HOST"):
        for ix in registry.get_indices():
            if not ix._mapping:
                continue

            fields = """
            frbr_uri_country
            frbr_uri_locality
            frbr_uri_place
            frbr_uri_doctype
            frbr_uri_subtype
            frbr_uri_actor
            """.split()
            body = {
                "properties": {
                    **{field: ix._mapping[field].to_dict() for field in fields}
                }
            }
            ix.connection.indices.put_mapping(
                index=ix._name,
                body=body,
            )


class Migration(migrations.Migration):

    dependencies = [("peachjam_search", "0019_es_mapping_add_summary")]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
