# Generated by Django 3.2.13 on 2022-06-30 09:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "peachjam",
            "0002_casenumber_judge_judgment_judgmentmediasummaryfile_mattertype",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="author",
            name="code",
            field=models.SlugField(max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name="author",
            name="name",
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
