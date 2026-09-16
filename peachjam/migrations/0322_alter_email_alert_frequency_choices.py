from django.db import migrations, models

import peachjam.models.user_profile


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0321_alter_peachjamsettings_allow_signups"),
    ]

    operations = [
        migrations.AlterField(
            model_name="peachjamsettings",
            name="email_alert_default_frequency",
            field=models.CharField(
                choices=[
                    ("daily", "Daily"),
                    ("weekly", "Weekly"),
                    ("monthly", "Monthly"),
                    ("none", "No email updates"),
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
                    ("none", "No email updates"),
                ],
                default=peachjam.models.user_profile.default_email_alert_frequency,
                help_text="How often to receive email notification digests.",
                max_length=16,
                verbose_name="email alert frequency",
            ),
        ),
    ]
