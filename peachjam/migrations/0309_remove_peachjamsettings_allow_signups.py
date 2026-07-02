from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0308_subscription_lock_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="peachjamsettings",
            name="allow_signups",
        ),
    ]
