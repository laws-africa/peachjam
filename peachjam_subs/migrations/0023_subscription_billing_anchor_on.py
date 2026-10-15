from datetime import timezone

from django.db import migrations, models


def preserve_existing_anniversaries(apps, schema_editor):
    Subscription = apps.get_model("peachjam_subs", "Subscription")
    subscriptions = Subscription.objects.using(schema_editor.connection.alias)
    for subscription in subscriptions.exclude(active_at=None).iterator():
        subscriptions.filter(pk=subscription.pk).update(
            billing_anchor_on=subscription.active_at.astimezone(timezone.utc).date()
        )


class Migration(migrations.Migration):
    dependencies = [("peachjam_subs", "0022_alter_organisationauditevent_event_type")]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="billing_anchor_on",
            field=models.DateField(blank=True, editable=False, null=True),
        ),
        migrations.RunPython(
            preserve_existing_anniversaries, migrations.RunPython.noop
        ),
    ]
