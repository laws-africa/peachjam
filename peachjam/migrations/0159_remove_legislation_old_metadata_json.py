# Generated by Django 4.2.15 on 2024-09-17 05:08

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0158_alter_legislation_old_metadata_json"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="legislation",
            name="old_metadata_json",
        ),
    ]
