from django.db import migrations, models

import peachjam.models.user_profile


def seed_site_default_frequency(apps, schema_editor):
    from django.conf import settings

    PeachJamSettings = apps.get_model("peachjam", "PeachJamSettings")
    site_settings, _ = PeachJamSettings.objects.get_or_create(pk=1)
    site_settings.email_alert_default_frequency = settings.PEACHJAM[
        "EMAIL_ALERT_DEFAULT_FREQUENCY"
    ]
    site_settings.save(update_fields=["email_alert_default_frequency"])


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0318_userprofile_email_alert_frequency"),
    ]

    operations = [
        migrations.AddField(
            model_name="peachjamsettings",
            name="email_alert_default_frequency",
            field=models.CharField(
                choices=[
                    ("daily", "Daily"),
                    ("weekly", "Weekly"),
                    ("monthly", "Monthly"),
                    ("none", "None"),
                ],
                default="daily",
                help_text="Default frequency for new users' email alert digests.",
                max_length=16,
                verbose_name="default email alert frequency",
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="email_alert_frequency",
            field=models.CharField(
                choices=[
                    ("daily", "Daily"),
                    ("weekly", "Weekly"),
                    ("monthly", "Monthly"),
                    ("none", "None"),
                ],
                default=peachjam.models.user_profile.default_email_alert_frequency,
                help_text="How often to receive email notification digests.",
                max_length=16,
                verbose_name="email alert frequency",
            ),
        ),
        migrations.RunPython(seed_site_default_frequency, migrations.RunPython.noop),
    ]
