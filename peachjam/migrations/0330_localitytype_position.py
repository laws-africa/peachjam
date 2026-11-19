from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0329_merge_locality_and_main"),
    ]

    operations = [
        migrations.AddField(
            model_name="localitytype",
            name="position",
            field=models.PositiveIntegerField(default=0, verbose_name="position"),
        ),
        migrations.AlterModelOptions(
            name="localitytype",
            options={
                "ordering": ("position", "pk"),
                "verbose_name": "locality type",
                "verbose_name_plural": "locality types",
            },
        ),
    ]
