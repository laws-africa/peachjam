# Generated by Django 4.2.14 on 2024-11-15 11:12

from django.db import migrations, models

from peachjam.models import Taxonomy


def backfill_path_name(apps, schema_editor):
    # deliberately use the actual Taxonomy model
    for taxonomy in Taxonomy.get_root_nodes():
        taxonomy.save()


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0180_taxonomy_show_in_document_listing"),
    ]

    operations = [
        migrations.AddField(
            model_name="taxonomy",
            name="path_name",
            field=models.CharField(
                blank=True, max_length=4096, verbose_name="path name"
            ),
        ),
        migrations.AddField(
            model_name="taxonomy",
            name="path_name_en",
            field=models.CharField(
                blank=True, max_length=4096, null=True, verbose_name="path name"
            ),
        ),
        migrations.AddField(
            model_name="taxonomy",
            name="path_name_fr",
            field=models.CharField(
                blank=True, max_length=4096, null=True, verbose_name="path name"
            ),
        ),
        migrations.AddField(
            model_name="taxonomy",
            name="path_name_pt",
            field=models.CharField(
                blank=True, max_length=4096, null=True, verbose_name="path name"
            ),
        ),
        migrations.AddField(
            model_name="taxonomy",
            name="path_name_sw",
            field=models.CharField(
                blank=True, max_length=4096, null=True, verbose_name="path name"
            ),
        ),
        migrations.RunPython(backfill_path_name, migrations.RunPython.noop),
    ]