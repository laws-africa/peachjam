# Generated by Django 3.2.19 on 2023-07-13 13:57

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0088_model_translations"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="judge",
            options={
                "ordering": ("pk", "name"),
                "verbose_name": "judge",
                "verbose_name_plural": "judges",
            },
        ),
    ]