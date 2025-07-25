import os

from django.db import migrations


def forwards(apps, schema_editor):
    from django.conf import settings
    from django_elasticsearch_dsl.registries import registry

    if not settings.DEBUG and os.environ.get("ELASTICSEARCH_HOST"):
        for ix in registry.get_indices():
            if not ix._mapping:
                continue
            print(f"Adding summary and blurb mapping for {ix._name}")
            ix.connection.indices.put_mapping(
                index=ix._name,
                body={
                    "properties": {
                        "summary": ix._mapping["summary"].to_dict(),
                        "blurb": ix._mapping["blurb"].to_dict(),
                    }
                },
            )


class Migration(migrations.Migration):

    dependencies = [("peachjam_search", "0018_savedsearch_a_and_more")]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
