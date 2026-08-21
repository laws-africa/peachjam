from django.db import migrations, models


def set_site_default_frequency(apps, schema_editor):
    from django.conf import settings

    UserProfile = apps.get_model("peachjam", "UserProfile")
    UserProfile.objects.update(
        email_alert_frequency=settings.PEACHJAM["EMAIL_ALERT_DEFAULT_FREQUENCY"]
    )


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0318_onboarding_profile"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="email_alert_frequency",
            field=models.CharField(
                choices=[
                    ("daily", "Daily"),
                    ("weekly", "Weekly"),
                    ("monthly", "Monthly"),
                    ("none", "None"),
                ],
                default="daily",
                help_text="How often to receive email notification digests.",
                max_length=16,
                verbose_name="email alert frequency",
            ),
        ),
        migrations.RunPython(set_site_default_frequency, migrations.RunPython.noop),
    ]
