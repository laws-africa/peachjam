from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("peachjam_search", "0027_es_mapping_add_locality_translations")]

    operations = [
        migrations.AddField(
            model_name="searchtrace",
            name="query_analysis",
            field=models.JSONField(null=True),
        ),
        migrations.AddField(
            model_name="searchtrace",
            name="search_profile",
            field=models.CharField(max_length=100, null=True),
        ),
    ]
