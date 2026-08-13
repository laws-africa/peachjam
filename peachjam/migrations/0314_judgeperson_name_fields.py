import re

from django.db import migrations, models

SURNAME_PARTICLES = {
    "da",
    "de",
    "del",
    "der",
    "di",
    "du",
    "la",
    "le",
    "van",
    "von",
}

JUDICIAL_TITLES = {
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


def strip_judicial_title(name):
    tokens = name.split()
    while tokens:
        max_size = min(3, len(tokens))
        for size in range(max_size, 0, -1):
            candidate = re.sub(r"[^A-Za-z]", "", "".join(tokens[-size:])).upper()
            if candidate in JUDICIAL_TITLES:
                tokens = tokens[:-size]
                break
        else:
            break
    return " ".join(tokens).rstrip(" ,.;:-")


def split_full_name(full_name):
    name = " ".join((full_name or "").split())
    if not name:
        return "", ""

    if "," in name:
        last_name, first_name = name.split(",", 1)
        return strip_judicial_title(first_name.strip()), last_name.strip()

    name = strip_judicial_title(name)

    parts = name.split()
    if len(parts) == 1:
        return "", name

    last_name_start = len(parts) - 1
    while (
        last_name_start > 0
        and parts[last_name_start - 1].rstrip(".").casefold() in SURNAME_PARTICLES
    ):
        last_name_start -= 1

    return " ".join(parts[:last_name_start]), " ".join(parts[last_name_start:])


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

    judge_people_by_name = {}
    for judge_person in JudgePerson.objects.order_by("pk").iterator():
        judge_person.first_name, judge_person.last_name = split_full_name(
            judge_person.full_name
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
    atomic = False

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
        migrations.RemoveField(
            model_name="judgeperson",
            name="full_name",
        ),
        migrations.AlterField(
            model_name="judgeperson",
            name="last_name",
            field=models.CharField(max_length=1024, verbose_name="last name"),
        ),
        migrations.AlterModelOptions(
            name="judgeperson",
            options={
                "ordering": ("last_name", "first_name", "pk"),
                "verbose_name": "judge",
                "verbose_name_plural": "judges",
            },
        ),
        migrations.AddConstraint(
            model_name="judgeperson",
            constraint=models.UniqueConstraint(
                fields=("first_name", "last_name"),
                name="unique_judge_person_name",
            ),
        ),
    ]
