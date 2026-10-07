from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0315_judgetitle"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="judgeperson",
            name="full_name",
        ),
        migrations.AlterField(
            model_name="judgeperson",
            name="last_name",
            field=models.CharField(max_length=1024, verbose_name="last name"),
        ),
        migrations.AlterModelOptions(
            name="judgeperson",
            options={
                "ordering": ("last_name", "first_name", "pk"),
                "verbose_name": "judge",
                "verbose_name_plural": "judges",
            },
        ),
        migrations.AddConstraint(
            model_name="judgeperson",
            constraint=models.UniqueConstraint(
                fields=("first_name", "last_name"),
                name="unique_judge_person_name",
            ),
        ),
        migrations.RemoveField(
            model_name="judgealias",
            name="title_abbreviation",
        ),
    ]
