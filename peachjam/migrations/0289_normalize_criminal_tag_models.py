from django.db import migrations, models

OFFENCE_CATEGORY_DESCRIPTIONS = {
    "Violence": "Offences involving physical force, injury, or threats of violence.",
    "Sexual and Gender-Based Violence": "Offences involving sexual harm, coercion, or gender-based abuse.",
    "Property": "Offences involving theft, damage, trespass, or unlawful interference with property.",
    "Financial and Economic": "Offences involving fraud, corruption, or unlawful financial gain.",
    "Public Order": "Offences involving disorder, disturbance, or disruption of public peace.",
    "State and Political": "Offences against the state, public authority, or political order.",
    "Justice System": "Offences affecting courts, investigations, evidence, or the administration of justice.",
    "Public Safety": "Offences creating danger to the public, transport, health, or general safety.",
    "Morality": "Offences historically framed around morality, decency, or prohibited conduct.",
}

OFFENCE_TAG_DESCRIPTIONS = {
    "child-targeted": "The offence definition specifically targets children as victims or protected persons.",
    "deception-based": "The offence definition depends on deceit, fraud, or false pretences.",
    "weapon-capable": "The offence definition can involve being armed or using a weapon.",
    "consent-related": "The offence definition turns on the absence, invalidity, or scope of consent.",
    "custody-related": "The offence definition involves detention, custody, guardianship, or lawful control.",
    "public-official-related": "The offence definition involves a public official, public service, or public office.",
    "omission-based": "The offence can be committed by failing to act where the law imposes a duty.",
    "inchoate": "The offence definition covers attempt, conspiracy, incitement, or another incomplete offence.",
}

CASE_TAG_DESCRIPTIONS = {
    "child-victim": "The judgment indicates the victim for this offence was a child.",
    "domestic-context": "The judgment places the offence in a family or household setting.",
    "intimate-partner-context": "The judgment indicates the parties were intimate partners.",
    "public-official-victim": "The judgment indicates the victim was a public official.",
    "multiple-victims": "The judgment indicates there was more than one victim for this offence.",
    "weapon-used": "The judgment indicates a weapon was actually used in this offence.",
    "group-offending": "The judgment indicates more than one offender participated.",
    "serious-injury": "The judgment indicates the offence caused serious bodily injury.",
    "fatality": "The judgment indicates the offence resulted in death.",
    "threats-used": "The judgment indicates threats were used in carrying out the offence.",
    "trust-relationship": "The judgment indicates a relationship of trust between offender and victim.",
    "deception-used": "The judgment indicates deception was used in carrying out the offence.",
    "identification-issue": "The judgment discusses identification evidence as a live issue.",
    "confession-issue": "The judgment discusses a confession or its admissibility as a live issue.",
    "circumstantial-evidence": "The judgment relies on or disputes circumstantial evidence.",
    "consent-disputed": "The judgment specifically treats consent as a disputed factual issue.",
}


def noop_reverse(apps, schema_editor):
    pass


def normalize_legacy_tag_array(tags):
    cleaned = []
    seen = set()

    for tag in tags or []:
        normalized = (tag or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        cleaned.append(normalized)
        seen.add(normalized)

    return cleaned


def get_matched_legacy_tags(tags, tag_map):
    normalized_names = normalize_legacy_tag_array(tags)
    return [tag_map[name] for name in normalized_names if name in tag_map]


def seed_criminal_vocab_models(apps, schema_editor):
    OffenceCategory = apps.get_model("peachjam", "OffenceCategory")
    OffenceTag = apps.get_model("peachjam", "OffenceTag")
    CaseTag = apps.get_model("peachjam", "CaseTag")

    for name, description in OFFENCE_CATEGORY_DESCRIPTIONS.items():
        OffenceCategory.objects.update_or_create(
            name=name,
            defaults={"description": description},
        )

    for name, description in OFFENCE_TAG_DESCRIPTIONS.items():
        OffenceTag.objects.update_or_create(
            name=name,
            defaults={"description": description},
        )

    for name, description in CASE_TAG_DESCRIPTIONS.items():
        CaseTag.objects.update_or_create(
            name=name,
            defaults={"description": description},
        )


def backfill_criminal_tag_m2m(apps, schema_editor):
    Offence = apps.get_model("peachjam", "Offence")
    OffenceTag = apps.get_model("peachjam", "OffenceTag")
    JudgmentOffence = apps.get_model("peachjam", "JudgmentOffence")
    CaseTag = apps.get_model("peachjam", "CaseTag")

    offence_tag_map = {tag.name: tag for tag in OffenceTag.objects.all()}
    case_tag_map = {tag.name: tag for tag in CaseTag.objects.all()}

    for offence in Offence.objects.all().iterator():
        matched_tags = get_matched_legacy_tags(offence.offence_tags, offence_tag_map)
        offence.tags.set(matched_tags)

    for judgment_offence in JudgmentOffence.objects.all().iterator():
        matched_tags = get_matched_legacy_tags(judgment_offence.case_tags, case_tag_map)
        judgment_offence.tags.set(matched_tags)


class Migration(migrations.Migration):

    dependencies = [
        ("peachjam", "0288_offencecategory_and_case_tags"),
    ]

    operations = [
        migrations.CreateModel(
            name="CaseTag",
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
                (
                    "name",
                    models.CharField(max_length=255, unique=True, verbose_name="name"),
                ),
                (
                    "description",
                    models.TextField(blank=True, verbose_name="description"),
                ),
            ],
            options={
                "verbose_name": "case tag",
                "verbose_name_plural": "case tags",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="OffenceTag",
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
                (
                    "name",
                    models.CharField(max_length=255, unique=True, verbose_name="name"),
                ),
                (
                    "description",
                    models.TextField(blank=True, verbose_name="description"),
                ),
            ],
            options={
                "verbose_name": "offence tag",
                "verbose_name_plural": "offence tags",
                "ordering": ("name",),
            },
        ),
        migrations.AddField(
            model_name="judgmentoffence",
            name="tags",
            field=models.ManyToManyField(
                blank=True,
                related_name="judgment_offences",
                to="peachjam.casetag",
                verbose_name="case tags",
            ),
        ),
        migrations.AddField(
            model_name="offence",
            name="tags",
            field=models.ManyToManyField(
                blank=True,
                related_name="offences",
                to="peachjam.offencetag",
                verbose_name="tags",
            ),
        ),
        migrations.RunPython(seed_criminal_vocab_models, noop_reverse),
        migrations.RunPython(backfill_criminal_tag_m2m, noop_reverse),
    ]
