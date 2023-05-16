import logging

from countries_plus.models import Country
from languages_plus.models import Language

from peachjam.models import (
    CoreDocument,
    DocumentContent,
    DocumentNature,
    Gazette,
    Locality,
    SourceFile,
)
from peachjam.plugins import plugins

from .adapters import Adapter

log = logging.getLogger(__name__)


@plugins.register("ingestor-adapter")
class GazetteAdapter(Adapter):
    def __init__(self, settings):
        super().__init__(settings)
        self.jurisdiction = self.settings["jurisdiction"]

    def check_for_updates(self, last_refreshed):
        log.info(
            f"Checking for new gazettes from Gazettes.Africa since {last_refreshed}"
        )

        # start building queryset for updated gazettes
        updated_qs = (
            CoreDocument.objects.filter(doc_type="gazette")
            .non_polymorphic()
            .using("gazettes_africa")
        )
        # start building queryset for deleted gazettes
        deleted_qs = Gazette.objects

        if "-" not in self.jurisdiction:
            # locality code not specified hence None e.g "ZA"
            updated_qs = updated_qs.filter(
                jurisdiction=self.jurisdiction, locality=None
            )
            deleted_qs = deleted_qs.filter(
                jurisdiction=self.jurisdiction, locality=None
            )
        else:
            updated_qs = updated_qs.filter(jurisdiction=self.jurisdiction.split("-")[0])
            deleted_qs = deleted_qs.filter(jurisdiction=self.jurisdiction.split("-")[0])

            # locality code present e.g. "ZA-gp"
            if self.jurisdiction.split("-")[1] != "*":
                locality_code = self.jurisdiction.split("-")[1]
                updated_qs = updated_qs.filter(locality__code=locality_code)
                deleted_qs = deleted_qs.filter(locality__code=locality_code)
            else:
                # fetch all localities for this jurisdiction e.g. "ZA-*"
                updated_qs = updated_qs.exclude(locality=None)
                deleted_qs = deleted_qs.exclude(locality=None)

        updated_qs = updated_qs.values_list("expression_frbr_uri", flat=True)

        deleted_qs = deleted_qs.exclude(
            expression_frbr_uri__in=list(updated_qs)
        ).values_list("expression_frbr_uri", flat=True)

        if last_refreshed:
            updated_qs = updated_qs.filter(updated_at__gt=last_refreshed)

        return updated_qs, deleted_qs

    def update_document(self, expression_frbr_uri):
        log.info(f"Updating new gazette {expression_frbr_uri}")

        ga_gazette = (
            CoreDocument.objects.filter(expression_frbr_uri=expression_frbr_uri)
            .using("gazettes_africa")
            .non_polymorphic()
            .first()
        )

        if ga_gazette:
            data = {
                "title": ga_gazette.title,
                "date": ga_gazette.date,
                "source_url": ga_gazette.source_url,
                "citation": ga_gazette.citation,
                "content_html_is_akn": ga_gazette.content_html_is_akn,
                "language": Language.objects.get(pk=ga_gazette.language.pk),
                "jurisdiction": Country.objects.get(pk=ga_gazette.jurisdiction.pk),
                "work_frbr_uri": ga_gazette.work_frbr_uri,
                "frbr_uri_subtype": ga_gazette.frbr_uri_subtype,
                "frbr_uri_actor": ga_gazette.frbr_uri_actor,
                "frbr_uri_date": ga_gazette.frbr_uri_date,
                "frbr_uri_number": ga_gazette.frbr_uri_number,
                "expression_frbr_uri": ga_gazette.expression_frbr_uri,
            }

            if ga_gazette.locality:
                data["locality"] = Locality.objects.get(code=ga_gazette.locality.code)

            if ga_gazette.nature:
                document_nature_name = " ".join(
                    [name for name in ga_gazette.nature.name.split("-")]
                ).capitalize()
                data["nature"] = DocumentNature.objects.get_or_create(
                    code=ga_gazette.nature.code,
                    defaults={"name": document_nature_name},
                )[0]

            updated_gazette, new = Gazette.objects.update_or_create(
                expression_frbr_uri=expression_frbr_uri, defaults={**data}
            )

            ga_source_file = (
                SourceFile.objects.filter(document=ga_gazette)
                .values("file", "filename", "size", "mimetype")
                .using("gazettes_africa")
            )

            file_path = ga_source_file[0].pop("file")

            if ga_source_file:
                source_url = f"https://gazettes.africa{expression_frbr_uri}/source"
                updated_source_file, _ = SourceFile.objects.update_or_create(
                    document=updated_gazette,
                    defaults={"file": f"{file_path}", "source_url": source_url},
                )
                # update the source file to include the bucket name
                updated_source_file.file.set_raw_value(file_path)

            if hasattr(ga_gazette, "document_content"):
                ga_content_text = ga_gazette.document_content.content_text
                DocumentContent.objects.update_or_create(
                    document=updated_gazette, content_text=ga_content_text
                )
            updated_gazette.extract_citations()

            log.info("Update Done.")

    def delete_document(self, expression_frbr_uri):
        ga_gazette = (
            CoreDocument.objects.filter(
                doc_type="gazette", expression_frbr_uri=expression_frbr_uri
            )
            .non_polymorphic()
            .using("gazettes_africa")
            .first()
        )
        local_gazette = Gazette.objects.filter(
            expression_frbr_uri=expression_frbr_uri
        ).first()
        if not ga_gazette and local_gazette:
            local_gazette.delete()
