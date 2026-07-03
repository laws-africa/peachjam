from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam_search", "0024_searchtrace_query_classification_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="savedsearch",
            name="subscription_locked_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="subscription locked at"
            ),
        ),
        migrations.AddField(
            model_name="savedsearch",
            name="subscription_lock_expires_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="subscription lock expires at"
            ),
        ),
    ]
