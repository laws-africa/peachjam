from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0295_judgment_flynote"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="flynote",
            name="slug",
        ),
    ]
