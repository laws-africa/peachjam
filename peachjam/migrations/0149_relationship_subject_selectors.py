# Generated by Django 3.2.25 on 2024-07-26 11:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0148_alter_judgment_auto_assign_details"),
    ]

    operations = [
        migrations.AddField(
            model_name="relationship",
            name="subject_selectors",
            field=models.JSONField(null=True, verbose_name="subject selectors"),
        ),
    ]
