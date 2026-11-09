from urllib.parse import parse_qs

from django.db import migrations, models
from django.db.models.functions import Lower, Trim


def transfer_history_removals(apps, schema_editor):
    """Keep removed simple searches hidden when history moves onto traces."""
    alias = schema_editor.connection.alias
    history = apps.get_model("peachjam_search", "SearchHistory")
    traces = apps.get_model("peachjam_search", "SearchTrace").objects.using(alias)
    eligible = traces.filter(
        models.Q(field_searches__isnull=True) | models.Q(field_searches={}),
        models.Q(filters__isnull=True) | models.Q(filters={}),
        models.Q(ordering__isnull=True) | models.Q(ordering__in=["", "-score"]),
        kind="documents",
        status="completed",
        page=1,
        mode="text",
    ).annotate(
        history_text=Lower(
            Trim(
                models.Func(
                    "search",
                    models.Value(r"\s+"),
                    models.Value(" "),
                    models.Value("g"),
                    function="REGEXP_REPLACE",
                    output_field=models.CharField(),
                )
            )
        )
    )
    defaults = {"page": "1", "ordering": "-score", "mode": "text"}
    allowed = {"q", "suggestion", "gsc.tab", *defaults}
    for entry in history.objects.using(alias).filter(removed=True).iterator():
        params = parse_qs(entry.query_string)
        if set(params) - allowed or not params.get("q"):
            continue
        if any(params.get(key, [value]) != [value] for key, value in defaults.items()):
            continue
        eligible.filter(
            user_id=entry.user_id,
            history_text=" ".join(params["q"][0].split()).lower(),
            created_at__lte=entry.updated_at,
        ).update(hidden=True)


class Migration(migrations.Migration):
    dependencies = [("peachjam_search", "0033_searchhistory_and_more")]

    operations = [
        migrations.AddField(
            model_name="searchtrace",
            name="hidden",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(transfer_history_removals, migrations.RunPython.noop),
        migrations.DeleteModel(name="SearchHistory"),
    ]
