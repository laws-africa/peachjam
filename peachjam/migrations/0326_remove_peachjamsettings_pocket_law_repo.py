from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0325_flynote_name_prefix_index"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="peachjamsettings",
            name="pocket_law_repo",
        ),
    ]
