import logging
import re
from datetime import datetime
from functools import cached_property, reduce
from tempfile import NamedTemporaryFile

import magic
import requests
from cobalt import FrbrUri
from countries_plus.models import Country
from dateutil import parser
from django.core.files import File
from django.db.models import Q
from django.utils.text import slugify
from languages_plus.models import Language

from peachjam.adapters.base import Adapter
from peachjam.models import (
    AlternativeName,
    Author,
    CoreDocument,
    DocumentNature,
    DocumentTopic,
    GenericDocument,
    Image,
    LegalInstrument,
    Legislation,
    Locality,
    Predicate,
    Relationship,
    Taxonomy,
    Work,
)
from peachjam.plugins import plugins

logger = logging.getLogger(__name__)


@plugins.register("ingestor-adapter")
class IndigoAdapter(Adapter):
    """Adapter that pulls data from the Indigo API.

    Settings:

    * token: API token
    * api_url: URL to API base (no ending slash)
    * places: space-separate list of place codes, such as: bw za-*
    """

    def __init__(self, settings):
        super().__init__(settings)
        self.client = requests.session()
        self.client.headers.update(
            {
                "Authorization": f"Token {self.settings['token']}",
            }
        )
        self.api_url = self.settings["api_url"]
        self.taxonomy_topic_root = self.settings.get("taxonomy_topic_root")

    def check_for_updates(self, last_refreshed):
        """Checks for documents updated since last_refreshed (which may be None), and returns a list
        of document identifiers (expression FRBR URIs) which must be updated.
        """
        docs = self.get_doc_list()
        updated_docs = self.check_for_updated(docs, last_refreshed)
        deleted_docs = self.check_for_deleted(docs)

        return updated_docs, deleted_docs

    def get_doc_list(self):
        results = []

        for place_code in self.place_codes:
            logger.info(f"Getting document list for {place_code}")
            url = f"{self.api_url}/akn/{place_code}/.json"
            while url:
                try:
                    res = self.client_get(url).json()
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 404:
                        logger.warning(f"Ignoring 404 for {url}")
                        continue
                    raise e

                # ignore bills
                # TODO: later, make this configurable
                res["results"] = [r for r in res["results"] if r["nature"] != "bill"]

                # Filter by actor, if setting is present
                actor = self.settings.get("actor", None)
                if actor:
                    results_filtered_by_actor = [
                        result for result in res["results"] if result["actor"] == actor
                    ]
                    results.extend(results_filtered_by_actor)
                    url = res["next"]
                else:
                    results.extend(res["results"])
                    url = res["next"]

        return results

    @cached_property
    def place_codes(self):
        """Get a list of place codes, based on the `places` setting.

        * za: just za
        * za-cpt: just za-cpt
        * za-*: all localities in za
        """
        codes = []

        for code in self.settings["places"].split():
            if code.endswith("-*"):
                place = code.split("-", 1)[0]
                codes.append(place)
                # get all localities for this place
                for loc in self.places[place]["localities"]:
                    # ignore playgrounds when expanding wildcards
                    if loc["code"] != "playground":
                        codes.append(loc["frbr_uri_code"])
                continue
            else:
                codes.append(code)

        return codes

    @cached_property
    def places(self):
        """Get place information from server as a dict from code to place info."""
        places = self.client_get(f"{self.api_url}/countries.json").json()["results"]
        return {p["code"]: p for p in places}

    def check_for_deleted(self, docs):
        uris = {d["expression_frbr_uri"] for d in docs}
        for doc in docs:
            for pit in doc["points_in_time"]:
                for expr in pit["expressions"]:
                    uris.add(expr["expression_frbr_uri"])

        # filter by place/locality codes
        places = []
        for code in self.place_codes:
            if "-" in code:
                country, locality = code.split("-", 1)
                places.append(
                    Q(jurisdiction__iso=country.upper(), locality__code=locality)
                )
            else:
                places.append(Q(jurisdiction__iso=code.upper(), locality__code=None))
        # combine the place queries with OR
        qs = Legislation.objects.filter(reduce(lambda a, b: a | b, places))

        return qs.exclude(expression_frbr_uri__in=list(uris)).values_list(
            "expression_frbr_uri", flat=True
        )

    def check_for_updated(self, docs, last_refreshed):
        docs = [
            document
            for document in docs
            if last_refreshed is None
            or parser.parse(document["updated_at"]) > last_refreshed
        ]

        urls = {d["url"] for d in docs}
        for doc in docs:
            # if a document is out of date, also ensure we update its other expressions
            for pit in doc["points_in_time"]:
                for expr in pit["expressions"]:
                    urls.add(expr["url"])

        return urls

    def update_document(self, url):
        logger.info(f"Updating document ... {url}")

        try:
            document = self.client_get(f"{url}.json").json()
        except requests.HTTPError as error:
            if error.response.status_code == 404:
                return
            else:
                raise error

        # don't ingest stubs that don't have a publication document
        if document["stub"]:
            pubdoc = document["publication_document"]
            if not pubdoc or not pubdoc["url"]:
                return

        frbr_uri = FrbrUri.parse(document["frbr_uri"])
        title = document["title"]
        toc_json = self.get_toc_json(url)
        jurisdiction = Country.objects.get(iso__iexact=document["country"])
        language = Language.objects.get(iso_639_2T__iexact=document["language"])

        field_data = {
            "title": title,
            "created_at": document["created_at"],
            "updated_at": document["updated_at"],
            "content_html_is_akn": True,
            "source_url": document["publication_document"]["url"]
            if document["publication_document"]
            else None,
            "language": language,
            "toc_json": toc_json,
            "content_html": self.get_content_html(document),
            "citation": document["numbered_title"],
        }

        frbr_uri_data = {
            "jurisdiction": jurisdiction,
            "frbr_uri_doctype": frbr_uri.doctype,
            "frbr_uri_subtype": frbr_uri.subtype,
            "frbr_uri_actor": frbr_uri.actor,
            "frbr_uri_number": frbr_uri.number,
            "frbr_uri_date": frbr_uri.date,
            "language": language,
            "date": datetime.strptime(document["expression_date"], "%Y-%m-%d").date(),
        }
        if document["locality"]:
            frbr_uri_data["locality"] = Locality.objects.get(code=document["locality"])

        doc = CoreDocument(**frbr_uri_data)
        doc.work_frbr_uri = doc.generate_work_frbr_uri()
        expression_frbr_uri = doc.generate_expression_frbr_uri()

        if frbr_uri.work_uri() != doc.work_frbr_uri:
            raise Exception("FRBR URIs do not match.")

        model = self.get_model(document)
        logger.info(f"Importing as {model}")

        if document["subtype"]:
            if document["type_name"]:
                document_nature_name = document["type_name"]
            else:
                document_nature_name = " ".join(
                    [name for name in document["subtype"].split("-")]
                ).capitalize()
            field_data["nature"] = DocumentNature.objects.update_or_create(
                code=slugify(document["subtype"]),
                defaults={"name": document_nature_name},
            )[0]

        if hasattr(model, "author") and frbr_uri.actor:
            field_data["author"] = Author.objects.get_or_create(
                code=frbr_uri.actor, defaults={"name": frbr_uri.actor}
            )[0]

        if hasattr(model, "metadata_json"):
            field_data["metadata_json"] = document

        if hasattr(model, "timeline_json") and not self.settings.get("skip_timeline"):
            timeline = self.client_get(f"{url}/timeline.json").json()
            field_data["timeline_json"] = timeline["timeline"]

        if hasattr(model, "commencements_json") and not self.settings.get(
            "skip_commencements"
        ):
            commencements_json = self.client_get(f"{url}/commencements.json").json()
            field_data["commencements_json"] = commencements_json["commencements"]

        if hasattr(model, "repealed") and document["repeal"]:
            field_data["repealed"] = True

        # the document may already be in the database, but not as the right document type.
        # It's unlikely, but does happen and is confusing to debug, so let's check for it explicitly.
        core_doc = CoreDocument.objects.filter(
            expression_frbr_uri=expression_frbr_uri
        ).first()
        existing_doc = model.objects.filter(
            expression_frbr_uri=expression_frbr_uri
        ).first()
        if core_doc and not existing_doc:
            raise Exception(
                f"The document {expression_frbr_uri} already exists as {core_doc.doc_type}"
                f" but not as {model}. Delete the existing document (CoreDocument #{core_doc.pk})."
            )

        created_doc, new = model.objects.update_or_create(
            expression_frbr_uri=expression_frbr_uri,
            defaults={**field_data, **frbr_uri_data},
        )

        logger.info(f"New document: {new}")

        if document["stub"]:
            # for stub documents, use the publication document as the source file
            pubdoc = document["publication_document"]
            if pubdoc and pubdoc["url"]:
                self.download_source_file(pubdoc["url"], created_doc, title)
        else:
            # the source file is the PDF version
            self.download_source_file(f"{url}.pdf", created_doc, title)

        if self.taxonomy_topic_root:
            # clear any existing taxonomies
            created_doc.taxonomies.filter(
                topic__slug__startswith=self.taxonomy_topic_root
            ).delete()

            if document["taxonomy_topics"]:
                # get topics beginning with "subject-areas"
                topics = [
                    t
                    for t in document["taxonomy_topics"]
                    if t.startswith(self.taxonomy_topic_root)
                ]
                if topics:
                    taxonomies = Taxonomy.objects.filter(slug__in=topics)
                    for taxonomy in taxonomies:
                        DocumentTopic.objects.create(
                            document=created_doc,
                            topic=taxonomy,
                        )
                    logger.info(f"Added {len(taxonomies)} taxonomies to {created_doc}")

        # fetch associated aliases
        self.fetch_and_create_aliases(document, created_doc)
        self.set_parent(document, created_doc)
        self.fetch_relationships(document, created_doc)
        self.download_and_save_document_images(document, created_doc)

    def list_images_from_content_api(self, document):
        links = document["links"]
        if links:
            for link in links:
                if link["href"].endswith("media.json"):
                    response = self.client_get(link["href"])
                    if response.json()["results"]:
                        return response.json()["results"]

    def download_and_save_document_images(self, document, created_document):
        # delete all existing images for the doc
        Image.objects.filter(document=created_document).delete()

        image_list = self.list_images_from_content_api(document)
        if image_list:
            for result in image_list:
                if result["mime_type"].startswith("image/"):
                    with NamedTemporaryFile() as file:
                        r = self.client_get(result["url"])
                        file.write(r.content)

                        Image.objects.create(
                            document=created_document,
                            file=File(file, name=result["filename"]),
                            mimetype=result["mime_type"],
                            filename=result["filename"],
                            size=result["size"],
                        )

            logger.info(f"Downloaded image(s) for {created_document}")

    def get_model(self, document):
        if document["nature"] == "act":
            if document["subtype"] in [
                "charter",
                "protocol",
                "convention",
                "treaty",
                "recommendation",
            ]:
                return LegalInstrument
            return Legislation
        return GenericDocument

    def set_parent(self, imported_document, created_document):
        # handle parent as a special relationship
        if imported_document["parent_work"]:
            parent_work, _ = Work.objects.get_or_create(
                frbr_uri=imported_document["parent_work"]["frbr_uri"],
                defaults={"title": imported_document["parent_work"]["title"]},
            )
            created_document.parent_work = parent_work
            logger.info(f"Set parent to {parent_work}")
        else:
            created_document.parent_work = None
        created_document.save()

    def remove_existing_relationships(self, subject_work):
        # delete any existing relationships first
        relationships = Relationship.objects.filter(
            subject_work=subject_work,
            predicate__slug__in=list(self.predicates.keys()),
        )
        logger.info(f"Deleting {relationships.count()} relationships")
        relationships.delete()

    def fetch_relationships(self, imported_document, created_document):
        subject_work = created_document.work
        self.remove_existing_relationships(subject_work)

        if imported_document["repeal"]:
            repealing_work, _ = Work.objects.get_or_create(
                frbr_uri=imported_document["repeal"]["repealing_uri"],
                defaults={"title": imported_document["repeal"]["repealing_title"]},
            )
            self.create_relationship(
                "repealed-by",
                subject_work=subject_work,
                object_work=repealing_work,
            )

        if imported_document.get("work_amendments") or imported_document.get(
            "amendments"
        ):
            amendments = (
                imported_document.get("work_amendments")
                or imported_document.get("amendments")
                or []
            )
            for amendment in amendments:
                if amendment["amending_uri"] and amendment["amending_title"]:
                    amending_work, _ = Work.objects.get_or_create(
                        frbr_uri=amendment["amending_uri"],
                        defaults={"title": amendment["amending_title"]},
                    )
                    self.create_relationship(
                        "amended-by",
                        subject_work=subject_work,
                        object_work=amending_work,
                    )

        if hasattr(created_document, "commencements_json"):
            commencements = created_document.commencements_json
            if commencements:
                for commencement in commencements:
                    if (
                        commencement["commencing_frbr_uri"]
                        and commencement["commencing_title"]
                    ):
                        commencing_work, _ = Work.objects.get_or_create(
                            frbr_uri=commencement["commencing_frbr_uri"],
                            defaults={"title": commencement["commencing_title"]},
                        )
                        self.create_relationship(
                            "commenced-by",
                            subject_work=subject_work,
                            object_work=commencing_work,
                        )
        logger.info(f"Fetching of relationships for {subject_work} is complete!")

    def create_relationship(self, slug, subject_work, object_work):
        predicate, created = Predicate.objects.get_or_create(
            slug=slug,
            defaults={
                "name": self.predicates[slug]["name"],
                "slug": slug,
                "verb": self.predicates[slug]["verb"],
                "reverse_verb": self.predicates[slug]["reverse_verb"],
            },
        )
        Relationship.objects.get_or_create(
            subject_work=subject_work,
            object_work=object_work,
            predicate=predicate,
        )
        logger.info(f"{self.predicates[slug]['name']} relationship created")

    def client_get(self, url):
        logger.debug(f"GET {url}")
        r = self.client.get(url)
        r.raise_for_status()
        return r

    def get_content_html(self, document):
        if document["stub"]:
            return None
        return self.client_get(document["url"] + ".html?resolver=none").text

    def get_toc_json(self, url):
        def remove_subparagraph(d):
            if d["type"] == "paragraph" or d["basic_unit"]:
                d["children"] = []
            else:
                for kid in d["children"]:
                    remove_subparagraph(kid)

        toc_json = self.client_get(url + "/toc.json").json()["toc"]
        for i in toc_json:
            remove_subparagraph(i)
        return toc_json

    def download_source_file(self, url, doc, title):
        from peachjam.models import SourceFile

        logger.info(f"Downloading source file from {url}")

        with NamedTemporaryFile() as f:
            r = self.client_get(url)
            try:
                # sometimes this header is not present
                d = r.headers["Content-Disposition"]
                filename = re.findall("filename=(.+)", d)[0]
            except KeyError:
                filename = f"{slugify(title)}.pdf"

            f.write(r.content)

            SourceFile.objects.update_or_create(
                document=doc,
                defaults={
                    "file": File(f, name=filename),
                    "mimetype": magic.from_file(f.name, mime=True),
                },
            )

    def delete_document(self, expression_frbr_uri):
        url = f"{self.api_url}{expression_frbr_uri}"

        try:
            document = self.client_get(url)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                document = CoreDocument.objects.filter(
                    expression_frbr_uri=expression_frbr_uri
                ).first()
                if document:
                    document.delete()
            else:
                raise e

    def fetch_and_create_aliases(self, document, created_document):
        aliases = document.get("aliases", [])
        if aliases:
            # delete all existing alternative names/aliases for doc
            AlternativeName.objects.filter(document=created_document).delete()

            for alias in aliases:
                AlternativeName.objects.create(document=created_document, title=alias)

            logger.info(f"Fetching of aliases for {created_document} is complete!")
