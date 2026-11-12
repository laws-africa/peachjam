from importlib import import_module

from django.db import migrations

demo_data = import_module("peachjam.migrations.0328_load_leading_authority_demo_data")


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0328_load_leading_authority_demo_data"),
    ]

    operations = [
        migrations.RunPython(demo_data.load_demo_data, migrations.RunPython.noop),
    ]
