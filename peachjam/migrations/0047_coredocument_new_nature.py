# Generated by Django 3.2.16 on 2023-02-09 09:34

from itertools import chain

import django.db.models.deletion
from django.db import migrations, models


def move_doc_nature(apps, schema_editor):
    GenericDocument = apps.get_model("peachjam", "GenericDocument")
    for doc in GenericDocument.objects.all().iterator(chunk_size=100):
        doc.new_nature = doc.nature
        doc.save()


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0046_alter_coredocument_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="coredocument",
            name="new_nature",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="peachjam.documentnature",
                verbose_name="nature",
            ),
        ),
        migrations.RunPython(move_doc_nature, migrations.RunPython.noop),
    ]
