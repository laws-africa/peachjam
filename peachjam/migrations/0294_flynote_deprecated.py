from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0293_judgment_flynote_raw"),
    ]

    operations = [
        migrations.AddField(
            model_name="flynote",
            name="deprecated",
            field=models.BooleanField(
                db_index=True, default=False, verbose_name="deprecated"
            ),
        ),
    ]
