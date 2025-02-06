import os

from django.db import migrations

from peachjam_search.documents import MultiLanguageIndexManager


def forwards(apps, schema_editor):
    from django.conf import settings
    from django_elasticsearch_dsl.registries import registry

    if not settings.DEBUG and os.environ.get("ELASTICSEARCH_HOST"):
        MultiLanguageIndexManager.get_instance().load_language_index_settings()

        for ix in registry.get_indices():
            if not ix._mapping:
                continue
            print(f"Adding suggest mapping for {ix._name}")
            ix.connection.indices.put_mapping(
                index=ix._name,
                body={"properties": {"suggest": ix._mapping["suggest"].to_dict()}},
            )


class Migration(migrations.Migration):

    dependencies = [("peachjam_search", "0007_searchtrace_suggestion")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
