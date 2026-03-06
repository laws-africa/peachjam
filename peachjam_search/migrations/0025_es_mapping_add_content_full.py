import os

from django.db import migrations


def forwards(apps, schema_editor):
    from django.conf import settings
    from django_elasticsearch_dsl.registries import registry

    if not settings.DEBUG and os.environ.get("ELASTICSEARCH_HOST"):
        for ix in registry.get_indices():
            if not ix._mapping:
                continue
            print(f"Adding content_full mapping for {ix._name}")
            ix.connection.indices.put_mapping(
                index=ix._name,
                body={
                    "properties": {
                        "content_full": ix._mapping["content_full"].to_dict(),
                    }
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam_search", "0024_searchtrace_query_classification_and_more")
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
