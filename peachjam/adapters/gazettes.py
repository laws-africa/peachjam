import logging
from datetime import date

import requests
from cobalt.uri import FrbrUri
from languages_plus.models import Language

from peachjam.models import Gazette, SourceFile, get_country_and_locality
from peachjam.plugins import plugins

from .base import Adapter

logger = logging.getLogger(__name__)


@plugins.register("ingestor-adapter")
class GazetteAPIAdapter(Adapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.jurisdiction = self.settings.get("jurisdiction")
        self.client = requests.session()
        self.client.headers.update(
            {
                "Authorization": f"Token {self.settings['token']}",
            }
        )
        self.api_url = self.settings["api_url"]

    def check_for_updates(self, last_refreshed):
        """Checks for documents updated since last_refreshed (which may be None), and returns a list
        of urls which must be updated.
        """
        docs = self.get_updated_docs(last_refreshed)
        urls = [d["url"] for d in docs]
        return urls, []

    def get_updated_docs(self, last_refreshed):
        results = []
        # self.jurisdiction can be a space-separated list of jurisdiction codes or an empty string for all jurisdictions
        for juri in (self.jurisdiction or "").split() or [None]:
            logger.info(
                f"Checking for new gazettes from Gazettes.Africa since {last_refreshed} for jurisdiction {juri}"
            )

            params = {}
            if last_refreshed:
                params["updated_at__gte"] = last_refreshed.isoformat()

            if juri:
                if juri.endswith("-*"):
                    # handle jurisdiction wildcards, eg za-*
                    # instead of asking for a jurisdiction code, we must ask for a specific
                    # country and all jurisdictions under it
                    params["country"] = juri.split("-")[0]
                    params["locality__isnull"] = False
                else:
                    params["jurisdiction"] = juri

            url = f"{self.api_url}/gazettes/archived.json"
            while url:
                res = self.client_get(url, params=params).json()
                params = {}
                results.extend(res["results"])
                url = res["next"]

        return results

    def update_document(self, url):
        logger.info(f"Updating gazette ... {url}")
        if url.endswith("/"):
            url = url[:-1]

        try:
            document = self.client_get(f"{url}.json").json()
        except requests.HTTPError as error:
            if error.response.status_code == 404:
                return
            else:
                raise error

        frbr_uri = FrbrUri.parse(document["expression_frbr_uri"])
        country, locality = get_country_and_locality(document["jurisdiction"])
        language = Language.objects.get(pk=document["language"])

        data = {
            "jurisdiction": country,
            "locality": locality,
            "frbr_uri_doctype": frbr_uri.doctype,
            "frbr_uri_subtype": frbr_uri.subtype,
            "frbr_uri_actor": frbr_uri.actor,
            "frbr_uri_number": frbr_uri.number,
            "frbr_uri_date": frbr_uri.date,
            "language": language,
            "date": date.fromisoformat(document["date"]),
            "title": document["name"],
            "publication": document["publication"],
            "sub_publication": document["sub_publication"],
            "supplement": document["supplement"],
            "supplement_number": document["supplement_number"],
            "part": document["part"],
            "key": document["key"],
            "created_at": document["created_at"],
            "updated_at": document["updated_at"],
        }
        gazette, new = Gazette.objects.update_or_create(
            expression_frbr_uri=document["expression_frbr_uri"],
            defaults={**data},
        )

        if frbr_uri.expression_uri() != gazette.expression_frbr_uri:
            raise Exception(
                f"FRBR URIs do not match: {frbr_uri.expression_uri()} != {gazette.expression_frbr_uri}"
            )

        logger.info(f"New document: {new}")

        s3_file = "s3:" + document["s3_location"].replace("/", ":", 1)
        sf, created = SourceFile.objects.update_or_create(
            document=gazette,
            defaults={
                "file": s3_file,
                "source_url": document["download_url"],
                "mimetype": "application/pdf",
                "filename": document["key"] + ".pdf",
                "size": document["size"],
            },
        )
        # force the dynamic file field to be set correctly
        SourceFile.objects.filter(pk=sf.pk).update(file=s3_file)

        logger.info("Done.")

    def delete_document(self, frbr_uri):
        url = f"{self.api_url}{frbr_uri}"

        try:
            self.client_get(url)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                document = Gazette.objects.filter(expression_frbr_uri=frbr_uri).first()
                if document:
                    document.delete()
            else:
                raise e

    def handle_webhook(self, data):
        from peachjam.tasks import delete_document, update_document

        logger.info(f"Ingestor {self.ingestor} handling webhook {data}")

        if data.get("action") == "updated" and data.get("gazette", {}).get("url"):
            logger.info("Will update document")
            update_document(self.ingestor.pk, data["gazette"]["url"])

        if data.get("action") == "deleted" and data.get("gazette", {}).get("frbr_uri"):
            logger.info("Will delete document")
            delete_document(self.ingestor.pk, data["gazette"]["frbr_uri"])

    def client_get(self, url, **kwargs):
        logger.debug(f"GET {url} kwargs={kwargs}")
        r = self.client.get(url, **kwargs)
        r.raise_for_status()
        return r
