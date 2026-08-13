import django.db.models.deletion
from django.db import migrations, models

TITLE_NAMES = {
    "ACJ": "Acting chief justice",
    "ACTJ": "Acting judge",
    "AJ": "Acting judge",
    "AJP": "Acting judge president",
    "AJA": "Acting judge of appeal",
    "AP": "Acting president",
    "CJ": "Chief justice",
    "CM": "Chief magistrate",
    "DCJ": "Deputy chief justice",
    "DJP": "Deputy judge president",
    "DR": "Deputy registrar",
    "J": "Judge",
    "JA": "Judge of appeal",
    "JCC": "Judge of the Constitutional Court",
    "JCS": "Judge of the Supreme Court",
    "JP": "Judge president",
    "JSC": "Justice of the Supreme Court",
    "P": "President",
    "PJ": "Presiding judge",
    "PM": "Principal magistrate",
    "R": "Registrar",
    "SCJ": "Supreme Court judge",
    "SCM": "Senior chief magistrate",
    "VP": "Vice president",
}


def normalize_title_abbreviation(value):
    return (value or "").strip().upper()


def create_titles_and_link_aliases(apps, schema_editor):
    JudgeAlias = apps.get_model("peachjam", "JudgeAlias")
    JudgeTitle = apps.get_model("peachjam", "JudgeTitle")

    abbreviations = {
        normalize_title_abbreviation(abbreviation)
        for abbreviation in JudgeAlias.objects.exclude(
            title_abbreviation=""
        ).values_list(
            "title_abbreviation",
            flat=True,
        )
    }
    abbreviations.discard("")
    abbreviations.update(TITLE_NAMES)
    titles = {}
    for abbreviation in sorted(abbreviations):
        title, _ = JudgeTitle.objects.get_or_create(
            abbreviation=abbreviation,
            defaults={"name": TITLE_NAMES.get(abbreviation, abbreviation)},
        )
        titles[abbreviation] = title

    for alias in JudgeAlias.objects.exclude(title_abbreviation="").iterator():
        alias.title_id = titles[
            normalize_title_abbreviation(alias.title_abbreviation)
        ].pk
        alias.save(update_fields=["title"])


def restore_alias_title_abbreviations(apps, schema_editor):
    JudgeAlias = apps.get_model("peachjam", "JudgeAlias")

    for alias in JudgeAlias.objects.select_related("title").iterator():
        alias.title_abbreviation = alias.title.abbreviation if alias.title_id else ""
        alias.save(update_fields=["title_abbreviation"])


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0314_judgeperson_name_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="JudgeTitle",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255, verbose_name="name")),
                (
                    "abbreviation",
                    models.CharField(
                        max_length=32,
                        unique=True,
                        verbose_name="abbreviation",
                    ),
                ),
            ],
            options={
                "verbose_name": "judicial title",
                "verbose_name_plural": "judicial titles",
                "ordering": ("name", "abbreviation"),
            },
        ),
        migrations.RenameField(
            model_name="judgealias",
            old_name="title",
            new_name="title_abbreviation",
        ),
        migrations.AddField(
            model_name="judgealias",
            name="title",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="aliases",
                to="peachjam.judgetitle",
                verbose_name="judicial title",
            ),
        ),
        migrations.RunPython(
            create_titles_and_link_aliases,
            reverse_code=restore_alias_title_abbreviations,
        ),
        migrations.RemoveField(
            model_name="judgealias",
            name="title_abbreviation",
        ),
    ]
