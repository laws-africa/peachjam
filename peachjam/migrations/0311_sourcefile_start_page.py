import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0310_locality_name_translations"),
    ]

    operations = [
        migrations.AddField(
            model_name="sourcefile",
            name="start_page",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="The page in the source PDF where this document starts.",
                null=True,
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name="start page",
            ),
        ),
    ]
