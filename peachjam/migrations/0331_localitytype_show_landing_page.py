from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0330_localitytype_position"),
    ]

    operations = [
        migrations.AddField(
            model_name="localitytype",
            name="show_landing_page",
            field=models.BooleanField(
                default=True,
                help_text="If disabled, open the locality's document listing directly.",
                verbose_name="show landing page",
            ),
        ),
    ]
