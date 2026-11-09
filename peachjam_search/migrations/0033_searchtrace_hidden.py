from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("peachjam_search", "0032_searchentityresult_searchentityclick")]

    operations = [
        migrations.AddField(
            model_name="searchtrace",
            name="hidden",
            field=models.BooleanField(default=False),
        ),
    ]
