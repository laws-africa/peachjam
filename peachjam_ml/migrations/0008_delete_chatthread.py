from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam_ml", "0007_alter_chatthread_user"),
    ]

    operations = [
        migrations.DeleteModel(name="ChatThread"),
    ]
