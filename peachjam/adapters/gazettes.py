import logging

from countries_plus.models import Country
from django.db import connection
from languages_plus.models import Language

from peachjam.models import CoreDocument, Gazette, Locality, SourceFile
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

        new_gazettes = (
            CoreDocument.objects.filter(
                doc_type="gazette", jurisdiction=self.jurisdiction.split("-")[-1]
            )
            .non_polymorphic()
            .using("gazettes_africa")
        )
        if last_refreshed:
            new_gazettes = new_gazettes.filter(updated_at__gt=last_refreshed)

        return list(new_gazettes.values_list("expression_frbr_uri", flat=True))

    def update_document(self, expression_frbr_uri):
        log.info("Updating new gazettes...")

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
                with connection.cursor() as cursor:
                    source_file_table = updated_source_file._meta.db_table
                    sql = f"""
                        UPDATE  {source_file_table}
                        SET file = '{file_path}'
                        WHERE id  = {updated_source_file.pk}
                        """
                    cursor.execute(sql)

            log.info("Update Done.")
