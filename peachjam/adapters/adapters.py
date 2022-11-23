import logging
import re
from datetime import datetime
from tempfile import NamedTemporaryFile

import magic
import requests
from cobalt import FrbrUri
from dateutil import parser
from django.core.files import File
from django.utils.text import slugify

from peachjam.models import CoreDocument, Predicate, Relationship, Work
from peachjam.plugins import plugins

logger = logging.getLogger(__name__)


class Adapter:
    def __init__(self, settings):
        self.settings = settings
        self.predicates = {
            "amended-by": {
                "name": "amended by",
                "verb": "is amended by",
                "reverse_verb": "amends",
            },
            "repealed-by": {
                "name": "repealed by",
                "verb": "is repealed by",
                "reverse_verb": "repeals",
            },
            "commenced-by": {
                "name": "commenced by",
                "verb": "is commenced by",
                "reverse_verb": "commences",
            },
        }

    def check_for_updates(self, last_refreshed):
        """Checks for documents updated since last_refreshed (which may be None), and returns a list
        of document identifiers (expression FRBR URIs) which must be updated.
        """
        raise NotImplementedError()

    def update_document(self, document_id):
        """Update the document identified by some opaque id, returned by check_for_updates."""
        raise NotImplementedError()

    @classmethod
    def name(cls):
        return cls.__name__


@plugins.register("ingestor-adapter")
class IndigoAdapter(Adapter):
    def __init__(self, settings):
        super().__init__(settings)
        self.client = requests.session()
        self.client.headers.update(
            {
                "Authorization": f"Token {self.settings['token']}",
            }
        )
        self.url = self.settings["url"]

    def check_for_updates(self, last_refreshed):
        """Checks for documents updated since last_refreshed (which may be None), and returns a list
        of document identifiers (expression FRBR URIs) which must be updated.
        """
        return self.get_updated_documents(last_refreshed)

    def get_doc_list(self):
        return self.client_get(self.url).json()["results"]

    def get_updated_documents(self, last_refreshed):
        docs = [
            document
            for document in self.get_doc_list()
            if last_refreshed is None
            or parser.parse(document["updated_at"]) > last_refreshed
        ]

        urls = []
        for doc in docs:
            # if a document is out of date, also ensure we update its other expressions
            for pit in doc["points_in_time"]:
                for expr in pit["expressions"]:
                    urls.append(expr["url"])

        return urls

    def update_document(self, url):
        from countries_plus.models import Country
        from languages_plus.models import Language

        from peachjam.models import (
            Author,
            CoreDocument,
            DocumentNature,
            GenericDocument,
            LegalInstrument,
            Legislation,
            Locality,
        )

        logger.info(f"Updating document ... {url}")

        try:
            document = self.client_get(f"{url}.json").json()
        except requests.HTTPError as error:
            if error.response.status_code == 404:
                return
            else:
                raise error

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
            "frbr_uri_subtype": frbr_uri.subtype,
            "frbr_uri_number": frbr_uri.number,
            "frbr_uri_doctype": frbr_uri.doctype,
            "frbr_uri_date": frbr_uri.date,
            "language": language,
            "date": datetime.strptime(document["expression_date"], "%Y-%m-%d").date(),
        }
        if document["locality"]:
            frbr_uri_data["locality"] = Locality.objects.get(code=document["locality"])

        if frbr_uri.actor:
            frbr_uri_data["frbr_uri_actor"] = frbr_uri.actor
            author, _ = Author.objects.get_or_create(
                code=frbr_uri.actor, defaults={"name": frbr_uri.actor}
            )
            field_data["author"] = author

        doc = CoreDocument(**frbr_uri_data)
        doc.work_frbr_uri = doc.generate_work_frbr_uri()
        expression_frbr_uri = doc.generate_expression_frbr_uri()

        if frbr_uri.work_uri() != doc.work_frbr_uri:
            raise Exception("FRBR URIs do not match.")

        if document["nature"] == "act":
            if document["subtype"] in ["charter", "protocol", "convention", "treaty"]:
                model = LegalInstrument
                field_data["nature"] = DocumentNature.objects.update_or_create(
                    code=document["subtype"], defaults={"name": document["subtype"]}
                )[0]
            else:
                model = Legislation
                field_data["metadata_json"] = document
        else:
            model = GenericDocument
            field_data["nature"] = DocumentNature.objects.update_or_create(
                code=document["subtype"], defaults={"name": document["subtype"]}
            )[0]

        logger.info(model)

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

        if document["repeal"] and isinstance(created_doc, Legislation):
            created_doc.repealed = True
            created_doc.save()

        logger.info(f"New document: {new}")

        if document["stub"]:
            # for stub documents, use the publication document as the source file
            pubdoc = document["publication_document"]
            if pubdoc and pubdoc["url"]:
                self.download_source_file(pubdoc["url"], created_doc, title)
        else:
            # the source file is the PDF version
            self.download_source_file(f"{url}.pdf", created_doc, title)

        self.set_parent(document, created_doc)
        self.fetch_relationships(document, created_doc)

    def set_parent(self, imported_document, created_document):
        # handle parent as a special relationship
        if imported_document["parent_work"]:
            parent_work, _ = Work.objects.get_or_create(
                frbr_uri=imported_document["parent_work"]["frbr_uri"],
                defaults={
                    "title": imported_document["parent_work"]["title"],
                    "languages": [imported_document["language"]],
                },
            )
            created_document.parent_work = parent_work
            logger.info(f"Set parent to {parent_work}")
        else:
            created_document.parent_work = None
        created_document.save()

    def fetch_relationships(self, imported_document, created_document):
        subject_work = created_document.work

        if imported_document["repeal"]:
            repealing_work, _ = Work.objects.get_or_create(
                frbr_uri=imported_document["repeal"]["repealing_uri"],
                defaults={
                    "title": imported_document["repeal"]["repealing_title"],
                    "languages": [imported_document["language"]],
                },
            )
            self.create_relationship(
                "repealed-by",
                subject_work=subject_work,
                object_work=repealing_work,
            )

        if imported_document["amendments"]:
            for amendment in imported_document["amendments"]:
                if amendment["amending_uri"] and amendment["amending_title"]:
                    amending_work, _ = Work.objects.get_or_create(
                        frbr_uri=amendment["amending_uri"],
                        defaults={
                            "title": amendment["amending_title"],
                            "languages": [imported_document["language"]],
                        },
                    )
                    self.create_relationship(
                        "amended-by",
                        subject_work=subject_work,
                        object_work=amending_work,
                    )

        if imported_document["commencements"]:
            for commencement in imported_document["commencements"]:
                if (
                    commencement["commencing_frbr_uri"]
                    and commencement["commencing_title"]
                ):
                    commencing_work, _ = Work.objects.get_or_create(
                        frbr_uri=commencement["commencing_frbr_uri"],
                        defaults={
                            "title": commencement["commencing_title"],
                            "languages": [imported_document["language"]],
                        },
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
        r = self.client.get(url)
        r.raise_for_status()
        return r

    def get_content_html(self, document):
        if document["stub"]:
            return None
        return self.client_get(document["url"] + ".html").text

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
        url = re.sub(r"/akn.*", expression_frbr_uri, self.url)
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
