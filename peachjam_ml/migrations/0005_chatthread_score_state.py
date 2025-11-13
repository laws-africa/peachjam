from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam_ml", "0004_chatthread"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatthread",
            name="score",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="chatthread",
            name="state_json",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
