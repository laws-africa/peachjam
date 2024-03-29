# Generated by Django 3.2.20 on 2024-02-23 12:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0119_matomo"),
    ]

    operations = [
        migrations.AddField(
            model_name="gazette",
            name="part",
            field=models.CharField(
                blank=True, max_length=10, null=True, verbose_name="part"
            ),
        ),
        migrations.AddField(
            model_name="gazette",
            name="publication",
            field=models.CharField(
                blank=True, max_length=100, null=True, verbose_name="publication"
            ),
        ),
        migrations.AddField(
            model_name="gazette",
            name="sub_publication",
            field=models.CharField(
                blank=True, max_length=100, null=True, verbose_name="sub publication"
            ),
        ),
        migrations.AddField(
            model_name="gazette",
            name="supplement",
            field=models.BooleanField(default=False, verbose_name="supplement"),
        ),
        migrations.AddField(
            model_name="gazette",
            name="supplement_number",
            field=models.IntegerField(
                blank=True, null=True, verbose_name="supplement number"
            ),
        ),
        migrations.AddField(
            model_name="gazette",
            name="key",
            field=models.CharField(
                max_length=512, null=True, blank=True, db_index=True, verbose_name="key"
            ),
        ),
    ]
