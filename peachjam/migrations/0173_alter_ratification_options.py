# Generated by Django 4.2.14 on 2024-10-28 14:18

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0172_alter_ingestor_options_delete_legalinstrument"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="ratification",
            options={
                "permissions": [("api_ratification", "API ratification access")],
                "verbose_name": "ratification",
                "verbose_name_plural": "ratifications",
            },
        ),
    ]
