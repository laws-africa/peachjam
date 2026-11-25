import django.db.models.deletion
from django.db import migrations, models


def seed_popular_legislation(apps, schema_editor):
    PeachJamSettings = apps.get_model("peachjam", "PeachJamSettings")
    PopularLegislation = apps.get_model("peachjam", "PopularLegislation")
    Work = apps.get_model("peachjam", "Work")
    database = schema_editor.connection.alias

    works = Work.objects.using(database).filter(
        documents__doc_type="legislation",
        documents__locality__isnull=True,
        documents__published=True,
    )
    site_settings = PeachJamSettings.objects.using(database).first()
    if site_settings:
        jurisdiction_id = site_settings.default_document_jurisdiction_id
        if jurisdiction_id is None:
            jurisdiction_ids = list(
                site_settings.document_jurisdictions.values_list("pk", flat=True)[:2]
            )
            if len(jurisdiction_ids) == 1:
                jurisdiction_id = jurisdiction_ids[0]
        if jurisdiction_id:
            works = works.filter(documents__jurisdiction_id=jurisdiction_id)
        else:
            return
    else:
        return

    popular_ordering = ("-authority_score", "-pagerank", "title")
    pinned_work_id = (
        works.filter(title__icontains="constitution")
        .exclude(title__icontains="amendment")
        .order_by(*popular_ordering)
        .values_list("pk", flat=True)
        .first()
    )
    works = works.annotate(
        popular_priority=models.Case(
            models.When(pk=pinned_work_id, then=models.Value(0)),
            default=models.Value(1),
            output_field=models.IntegerField(),
        )
    ).order_by("popular_priority", *popular_ordering)
    work_ids = list(works.values_list("pk", flat=True).distinct()[:10])
    PopularLegislation.objects.using(database).bulk_create(
        [
            PopularLegislation(work_id=work_id, position=position)
            for position, work_id in enumerate(work_ids, start=1)
        ]
    )


class Migration(migrations.Migration):
    dependencies = [
        ("peachjam", "0329_clear_gazette_source_urls"),
    ]

    operations = [
        migrations.CreateModel(
            name="PopularLegislation",
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
                    "position",
                    models.PositiveIntegerField(default=0, verbose_name="position"),
                ),
                (
                    "work",
                    models.OneToOneField(
                        limit_choices_to={
                            "documents__doc_type": "legislation",
                            "documents__published": True,
                        },
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="popular_legislation",
                        to="peachjam.work",
                        verbose_name="legislation",
                    ),
                ),
            ],
            options={
                "verbose_name": "popular legislation",
                "verbose_name_plural": "popular legislation",
                "ordering": ("position", "pk"),
            },
        ),
        migrations.RunPython(seed_popular_legislation, migrations.RunPython.noop),
        migrations.CreateModel(
            name="LocalityType",
            fields=[
                (
                    "position",
                    models.PositiveIntegerField(default=0, verbose_name="position"),
                ),
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
                    "name_en",
                    models.CharField(
                        max_length=255, null=True, unique=True, verbose_name="name"
                    ),
                ),
                (
                    "name_fr",
                    models.CharField(
                        max_length=255, null=True, unique=True, verbose_name="name"
                    ),
                ),
                (
                    "name_pt",
                    models.CharField(
                        max_length=255, null=True, unique=True, verbose_name="name"
                    ),
                ),
                (
                    "name_sw",
                    models.CharField(
                        max_length=255, null=True, unique=True, verbose_name="name"
                    ),
                ),
                ("code", models.SlugField(unique=True, verbose_name="code")),
                (
                    "legislation_title",
                    models.CharField(
                        default="legislation",
                        help_text="Heading suffix, for example legislation or By-laws.",
                        max_length=255,
                        verbose_name="legislation title",
                    ),
                ),
                (
                    "legislation_title_en",
                    models.CharField(
                        default="legislation",
                        help_text="Heading suffix, for example legislation or By-laws.",
                        max_length=255,
                        null=True,
                        verbose_name="legislation title",
                    ),
                ),
                (
                    "legislation_title_fr",
                    models.CharField(
                        default="legislation",
                        help_text="Heading suffix, for example legislation or By-laws.",
                        max_length=255,
                        null=True,
                        verbose_name="legislation title",
                    ),
                ),
                (
                    "legislation_title_pt",
                    models.CharField(
                        default="legislation",
                        help_text="Heading suffix, for example legislation or By-laws.",
                        max_length=255,
                        null=True,
                        verbose_name="legislation title",
                    ),
                ),
                (
                    "legislation_title_sw",
                    models.CharField(
                        default="legislation",
                        help_text="Heading suffix, for example legislation or By-laws.",
                        max_length=255,
                        null=True,
                        verbose_name="legislation title",
                    ),
                ),
                (
                    "collection_title",
                    models.CharField(
                        help_text="For example Provincial legislation or Municipal by-laws.",
                        max_length=255,
                        verbose_name="collection title",
                    ),
                ),
                (
                    "collection_title_en",
                    models.CharField(
                        help_text="For example Provincial legislation or Municipal by-laws.",
                        max_length=255,
                        null=True,
                        verbose_name="collection title",
                    ),
                ),
                (
                    "collection_title_fr",
                    models.CharField(
                        help_text="For example Provincial legislation or Municipal by-laws.",
                        max_length=255,
                        null=True,
                        verbose_name="collection title",
                    ),
                ),
                (
                    "collection_title_pt",
                    models.CharField(
                        help_text="For example Provincial legislation or Municipal by-laws.",
                        max_length=255,
                        null=True,
                        verbose_name="collection title",
                    ),
                ),
                (
                    "collection_title_sw",
                    models.CharField(
                        help_text="For example Provincial legislation or Municipal by-laws.",
                        max_length=255,
                        null=True,
                        verbose_name="collection title",
                    ),
                ),
                (
                    "show_subsidiary_legislation",
                    models.BooleanField(
                        default=True, verbose_name="show subsidiary legislation"
                    ),
                ),
                (
                    "show_document_nature",
                    models.BooleanField(
                        default=True, verbose_name="show document nature"
                    ),
                ),
            ],
            options={
                "verbose_name": "locality type",
                "verbose_name_plural": "locality types",
                "ordering": ("position", "pk"),
            },
        ),
        migrations.AddField(
            model_name="locality",
            name="locality_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="localities",
                to="peachjam.localitytype",
                verbose_name="locality type",
            ),
        ),
    ]
