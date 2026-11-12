from datetime import date

from django.db import migrations
from django.utils.text import slugify

REVIEW_DATE = date(2026, 10, 14)

AUTHORITIES = (
    (
        "/akn/za/judgment/zacc/1995/3/eng@1995-06-06",
        "Unconstitutionality of the death penalty; primacy of life and dignity; ubuntu",
    ),
    (
        "/akn/za/judgment/zacc/1997/12/eng@1997-10-07",
        'Test for unfair discrimination (the "Harksen test")',
    ),
    (
        "/akn/za/judgment/zacc/2000/19/eng@2000-10-04",
        "Reasonableness review of measures to realise socio-economic rights",
    ),
    (
        "/akn/za/judgment/zacc/2000/1/eng@2000-02-25",
        "Principle of legality and rationality",
    ),
    (
        "/akn/za/judgment/zacc/2004/15/eng@2004-03-12",
        "Reasonableness review under PAJA section 6(2)(h)",
    ),
    (
        "/akn/za/judgment/zasca/2004/48/eng@2004-05-28",
        "An unlawful act stands and has effect until set aside",
    ),
    (
        "/akn/za/judgment/zacc/2004/7/eng@2004-10-01",
        'The "just and equitable" approach to evictions under PIE',
    ),
    (
        "/akn/za/judgment/zacc/2001/22/eng@2001-08-16",
        "Development of common law; state duty to protect; omissions",
    ),
    (
        "/akn/za/judgment/zasca/1998/94/eng@1998-09-29",
        'Reasonable-publication defence (the "Bogoshi defence")',
    ),
    (
        "/akn/za/judgment/zasca/2012/13/eng@2012-03-16",
        "Unitary approach to interpreting statutes and documents",
    ),
    (
        "/akn/za/judgment/zacc/2007/5/eng@2007-04-04",
        "Public policy and constitutional control of pacta sunt servanda",
    ),
    (
        "/akn/za/judgment/zasca/2001/30/eng@2001-03-19",
        '"Substantial and compelling circumstances" in minimum sentencing',
    ),
    (
        "/akn/za/judgment/zacc/2007/22/eng@2007-10-05",
        "Reasonableness standard for reviewing CCMA awards",
    ),
)


def load_demo_data(apps, schema_editor):
    Judgment = apps.get_model("peachjam", "Judgment")
    LeadingAuthority = apps.get_model("peachjam", "LeadingAuthority")
    LegalSubject = apps.get_model("peachjam", "LegalSubject")

    judgments = iter(
        Judgment.objects.filter(
            published=True,
            expression_frbr_uri__startswith="/akn/za/judgment/",
        )
        .exclude(expression_frbr_uri="")
        .order_by("-date", "pk")[: len(AUTHORITIES)]
    )

    for _uri, subject_name in AUTHORITIES:
        subject, _ = LegalSubject.objects.get_or_create(
            name=subject_name,
            defaults={
                "slug": slugify(subject_name),
                "subject_type": "doctrine",
            },
        )
        if LeadingAuthority.objects.filter(subject=subject).exists():
            continue

        judgment = next(judgments, None)
        if judgment is None:
            continue

        LeadingAuthority.objects.get_or_create(
            judgment=judgment,
            subject=subject,
            defaults={
                "editorial_note": f"Leading authority for {subject_name}.",
                "reviewed_on": REVIEW_DATE,
                "published": True,
            },
        )


def unload_demo_data(apps, schema_editor):
    LeadingAuthority = apps.get_model("peachjam", "LeadingAuthority")
    LegalSubject = apps.get_model("peachjam", "LegalSubject")

    for _uri, subject_name in AUTHORITIES:
        LeadingAuthority.objects.filter(
            subject__name=subject_name,
            editorial_note=f"Leading authority for {subject_name}.",
            reviewed_on=REVIEW_DATE,
            published=True,
        ).delete()

    LegalSubject.objects.filter(
        name__in=[subject_name for _uri, subject_name in AUTHORITIES],
        leading_authorities__isnull=True,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0327_leadingauthority_legalsubject_and_more"),
    ]

    operations = [
        migrations.RunPython(load_demo_data, unload_demo_data),
    ]
