import re

from django.db import migrations, models

LEGACY_JUDICIAL_TITLES = {
    "AG",
    "ACJ",
    "ACTJ",
    "AJ",
    "AJP",
    "AJA",
    "AP",
    "CJ",
    "CM",
    "DCJ",
    "DJP",
    "DR",
    "J",
    "JA",
    "JCC",
    "JCS",
    "JP",
    "JSC",
    "P",
    "PJ",
    "PM",
    "R",
    "SCJ",
    "SCM",
    "VP",
}


def strip_judicial_title(name, judicial_titles):
    tokens = name.split()
    while tokens:
        max_size = min(3, len(tokens))
        for size in range(max_size, 0, -1):
            candidate = re.sub(r"[^A-Za-z]", "", "".join(tokens[-size:])).upper()
            if candidate in judicial_titles:
                tokens = tokens[:-size]
                break
        else:
            break
    return " ".join(tokens).rstrip(" ,.;:-")


def split_full_name(full_name, judicial_titles):
    name = " ".join((full_name or "").split())
    if not name:
        return "", ""

    if "," in name:
        last_name, first_name = name.split(",", 1)
        return (
            strip_judicial_title(first_name.strip(), judicial_titles),
            last_name.strip(),
        )

    name = strip_judicial_title(name, judicial_titles)

    parts = name.split()
    if len(parts) == 1:
        return "", name

    return parts[0], " ".join(parts[1:])


def move_related_judge_data(source, target, JudgeAlias, Bench):
    JudgeAlias.objects.filter(judge_person=source).update(judge_person=target)
    Bench.objects.filter(judge_person=source).update(judge_person=target)
    if not target.description and source.description:
        target.description = source.description
        target.save(update_fields=["description"])


def split_existing_full_names(apps, schema_editor):
    JudgePerson = apps.get_model("peachjam", "JudgePerson")
    JudgeAlias = apps.get_model("peachjam", "JudgeAlias")
    Bench = apps.get_model("peachjam", "Bench")
    configured_titles = {
        re.sub(r"[^A-Za-z]", "", title).upper()
        for title in JudgeAlias.objects.exclude(title="").values_list(
            "title", flat=True
        )
    }
    configured_titles.discard("")
    judicial_titles = LEGACY_JUDICIAL_TITLES | configured_titles

    judge_people_by_name = {}
    for judge_person in JudgePerson.objects.order_by("pk").iterator():
        judge_person.first_name, judge_person.last_name = split_full_name(
            judge_person.full_name, judicial_titles
        )
        judge_person.save(update_fields=["first_name", "last_name"])

        key = (
            judge_person.first_name.casefold(),
            judge_person.last_name.casefold(),
        )
        existing = judge_people_by_name.get(key)
        if existing is None:
            judge_people_by_name[key] = judge_person
            continue

        move_related_judge_data(judge_person, existing, JudgeAlias, Bench)
        judge_person.delete()


def restore_full_names(apps, schema_editor):
    JudgePerson = apps.get_model("peachjam", "JudgePerson")

    for judge_person in JudgePerson.objects.order_by("pk").iterator():
        judge_person.full_name = " ".join(
            part for part in (judge_person.first_name, judge_person.last_name) if part
        )
        judge_person.save(update_fields=["full_name"])


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0313_mark_external_citation_links_manual"),
    ]

    operations = [
        migrations.AddField(
            model_name="judgeperson",
            name="first_name",
            field=models.CharField(
                blank=True, max_length=1024, verbose_name="first name"
            ),
        ),
        migrations.AddField(
            model_name="judgeperson",
            name="last_name",
            field=models.CharField(
                blank=True, max_length=1024, verbose_name="last name"
            ),
        ),
        migrations.AlterField(
            model_name="judgeperson",
            name="full_name",
            field=models.CharField(
                max_length=1024,
                null=True,
                unique=True,
                verbose_name="full name",
            ),
        ),
        migrations.RunPython(
            split_existing_full_names,
            reverse_code=restore_full_names,
        ),
    ]
