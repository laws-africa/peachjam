# Generated by Django 3.2.21 on 2024-05-15 13:59

import os

from django.db import migrations


def forwards(apps, schema_editor):
    from django.conf import settings
    from django_elasticsearch_dsl.registries import registry

    if not settings.DEBUG and os.environ.get("ELASTICSEARCH_HOST"):
        for ix in registry.get_indices():
            if not ix._mapping:
                continue
            print(f"Adding outcome mapping for {ix._name}")
            ix.connection.indices.put_mapping(
                index=ix._name,
                body={
                    "properties": {
                        "outcome": ix._mapping["outcome"].to_dict(),
                        "outcome_en": ix._mapping["outcome_en"].to_dict(),
                        "outcome_sw": ix._mapping["outcome_sw"].to_dict(),
                        "outcome_fr": ix._mapping["outcome_fr"].to_dict(),
                        "outcome_pt": ix._mapping["outcome_pt"].to_dict(),
                        "order": ix._mapping["order"].to_dict(),
                    }
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0131_rename_order_outcome"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
