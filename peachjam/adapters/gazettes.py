import logging

from countries_plus.models import Country
from languages_plus.models import Language

from peachjam.models import CoreDocument, Gazette, Locality
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
        # if last_refreshed:
        #     new_gazettes = CoreDocument.objects.filter(
        #         jurisdiction=self.jurisdiction,
        #         updated_at__gt=last_refreshed
        #     ).non_polymorphic().using("gazettes_africa")[:5]
        # else:
        new_gazettes = (
            CoreDocument.objects.filter(
                jurisdiction=self.jurisdiction,
            )
            .non_polymorphic()
            .using("gazettes_africa")[:5]
        )

        print(new_gazettes)

        return list(new_gazettes.values_list("expression_frbr_uri", flat=True))

    def update_document(self, expression_frbr_uri):
        log.info("Updating new gazettes...")

        document = (
            CoreDocument.objects.filter(expression_frbr_uri=expression_frbr_uri)
            .using("gazettes_africa")
            .non_polymorphic()
            .first()
        )

        if document:
            data = {
                "title": document.title,
                "date": document.date,
                "source_url": document.source_url,
                "citation": document.citation,
                "content_html_is_akn": document.content_html_is_akn,
                "language": Language.objects.get(pk=document.language.pk),
                "jurisdiction": Country.objects.get(pk=document.jurisdiction.pk),
                "work_frbr_uri": document.work_frbr_uri,
                "frbr_uri_subtype": document.frbr_uri_subtype,
                "frbr_uri_actor": document.frbr_uri_actor,
                "frbr_uri_date": document.frbr_uri_date,
                "frbr_uri_number": document.frbr_uri_number,
                "expression_frbr_uri": document.expression_frbr_uri,
            }

            if document.locality:
                data["locality"] = Locality.objects.get(code=document.locality.code)

            doc, new = Gazette.objects.update_or_create(
                expression_frbr_uri=expression_frbr_uri, defaults={**data}
            )

            log.info(f"New Document {new}")
            log.info("Update Done.")

            return
