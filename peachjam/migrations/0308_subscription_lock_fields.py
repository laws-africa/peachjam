from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("peachjam", "0307_merge_20260626_0745")]

    operations = [
        migrations.AddField(
            model_name="folder",
            name="subscription_locked_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="subscription locked at"
            ),
        ),
        migrations.AddField(
            model_name="folder",
            name="subscription_lock_expires_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="subscription lock expires at"
            ),
        ),
        migrations.AddField(
            model_name="saveddocument",
            name="subscription_locked_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="subscription locked at"
            ),
        ),
        migrations.AddField(
            model_name="saveddocument",
            name="subscription_lock_expires_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="subscription lock expires at"
            ),
        ),
        migrations.AddField(
            model_name="userfollowing",
            name="subscription_locked_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="subscription locked at"
            ),
        ),
        migrations.AddField(
            model_name="userfollowing",
            name="subscription_lock_expires_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="subscription lock expires at"
            ),
        ),
    ]
