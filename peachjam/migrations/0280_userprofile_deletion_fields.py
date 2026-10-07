from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0279_remove_flynote_taxonomy_root"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="deleted_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="deleted at"
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="deleted_reason",
            field=models.TextField(
                blank=True, null=True, verbose_name="deleted reason"
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="email_hash",
            field=models.CharField(
                blank=True,
                max_length=64,
                null=True,
                verbose_name="email hash",
            ),
        ),
    ]
