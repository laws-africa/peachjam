import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0290_remove_legacy_criminal_tag_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="judgment",
            name="court",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="peachjam.court",
                verbose_name="court",
            ),
        ),
    ]
