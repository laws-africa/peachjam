from datetime import date

from django.db import migrations
from django.utils.text import slugify

REVIEW_DATE = date(2026, 10, 14)

AUTHORITIES = (
    (
        "/akn/za/judgment/zacc/1995/3/eng@1995-06-06",
        "Unconstitutionality of the death penalty; primacy of life and dignity; ubuntu",
        "S v Makwanyane 1995 (3) SA 391 (CC)",
    ),
    (
        "/akn/za/judgment/zacc/1997/12/eng@1997-10-07",
        'Test for unfair discrimination (the "Harksen test")',
        "Harksen v Lane NO 1998 (1) SA 300 (CC)",
    ),
    (
        "/akn/za/judgment/zacc/2000/19/eng@2000-10-04",
        "Reasonableness review of measures to realise socio-economic rights",
        "Government of the RSA v Grootboom 2001 (1) SA 46 (CC)",
    ),
    (
        "/akn/za/judgment/zacc/2000/1/eng@2000-02-25",
        "Principle of legality and rationality",
        "Pharmaceutical Manufacturers Association of SA: In re Ex parte President "
        "of the Republic of South Africa 2000 (2) SA 674 (CC)",
    ),
    (
        "/akn/za/judgment/zacc/2004/15/eng@2004-03-12",
        "Reasonableness review under PAJA section 6(2)(h)",
        "Bato Star Fishing (Pty) Ltd v Minister of Environmental Affairs and Tourism "
        "2004 (4) SA 490 (CC)",
    ),
    (
        "/akn/za/judgment/zasca/2004/48/eng@2004-05-28",
        "An unlawful act stands and has effect until set aside",
        "Oudekraal Estates (Pty) Ltd v City of Cape Town 2004 (6) SA 222 (SCA)",
    ),
    (
        "/akn/za/judgment/zacc/2004/7/eng@2004-10-01",
        'The "just and equitable" approach to evictions under PIE',
        "Port Elizabeth Municipality v Various Occupiers 2005 (1) SA 217 (CC)",
    ),
    (
        "/akn/za/judgment/zacc/2001/22/eng@2001-08-16",
        "Development of common law; state duty to protect; omissions",
        "Carmichele v Minister of Safety and Security 2001 (4) SA 938 (CC)",
    ),
    (
        "/akn/za/judgment/zasca/1998/94/eng@1998-09-29",
        'Reasonable-publication defence (the "Bogoshi defence")',
        "National Media Ltd v Bogoshi 1998 (4) SA 1196 (SCA)",
    ),
    (
        "/akn/za/judgment/zasca/2012/13/eng@2012-03-16",
        "Unitary approach to interpreting statutes and documents",
        "Natal Joint Municipal Pension Fund v Endumeni Municipality 2012 (4) SA 593 "
        "(SCA)",
    ),
    (
        "/akn/za/judgment/zacc/2007/5/eng@2007-04-04",
        "Public policy and constitutional control of pacta sunt servanda",
        "Barkhuizen v Napier 2007 (5) SA 323 (CC)",
    ),
    (
        "/akn/za/judgment/zasca/2001/30/eng@2001-03-19",
        '"Substantial and compelling circumstances" in minimum sentencing',
        "S v Malgas 2001 (1) SACR 469 (SCA)",
    ),
    (
        "/akn/za/judgment/zacc/2007/22/eng@2007-10-05",
        "Reasonableness standard for reviewing CCMA awards",
        "Sidumo v Rustenburg Platinum Mines Ltd 2008 (2) SA 24 (CC)",
    ),
)


def load_demo_data(apps, schema_editor):
    Judgment = apps.get_model("peachjam", "Judgment")
    LeadingAuthority = apps.get_model("peachjam", "LeadingAuthority")
    LeadingAuthoritySource = apps.get_model("peachjam", "LeadingAuthoritySource")
    LegalSubject = apps.get_model("peachjam", "LegalSubject")

    for uri, subject_name, citation in AUTHORITIES:
        judgment = Judgment.objects.filter(expression_frbr_uri=uri).first()
        if judgment is None:
            continue

        subject, _ = LegalSubject.objects.get_or_create(
            name=subject_name,
            defaults={
                "slug": slugify(subject_name),
                "subject_type": "doctrine",
            },
        )
        authority, _ = LeadingAuthority.objects.get_or_create(
            judgment=judgment,
            subject=subject,
            defaults={
                "editorial_note": f"Leading authority for {subject_name}.",
                "as_at_date": REVIEW_DATE,
                "published": True,
            },
        )
        LeadingAuthoritySource.objects.get_or_create(
            leading_authority=authority,
            citation=citation,
            defaults={"url": f"https://lawlibrary.org.za{uri}"},
        )


def unload_demo_data(apps, schema_editor):
    LeadingAuthority = apps.get_model("peachjam", "LeadingAuthority")
    LegalSubject = apps.get_model("peachjam", "LegalSubject")

    for uri, subject_name, _citation in AUTHORITIES:
        LeadingAuthority.objects.filter(
            judgment__expression_frbr_uri=uri,
            subject__name=subject_name,
            editorial_note=f"Leading authority for {subject_name}.",
            as_at_date=REVIEW_DATE,
            published=True,
        ).delete()

    LegalSubject.objects.filter(
        name__in=[subject_name for _uri, subject_name, _citation in AUTHORITIES],
        leading_authorities__isnull=True,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0326_leadingauthority_legalsubject_and_more"),
    ]

    operations = [
        migrations.RunPython(load_demo_data, unload_demo_data),
    ]
