# Generated by Django 3.2.19 on 2023-07-25 14:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0092_documentcontent_content_xml"),
    ]

    operations = [
        migrations.CreateModel(
            name="Label",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(max_length=1024, unique=True, verbose_name="name"),
                ),
                (
                    "code",
                    models.SlugField(max_length=1024, unique=True, verbose_name="code"),
                ),
            ],
        ),
        migrations.AddField(
            model_name="coredocument",
            name="labels",
            field=models.ManyToManyField(
                blank=True, to="peachjam.Label", verbose_name="labels"
            ),
        ),
    ]