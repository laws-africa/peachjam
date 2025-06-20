import dataclasses

from django.conf import settings
from django.utils.html import escape
from rest_framework.serializers import ModelSerializer

from peachjam.models import CoreDocument
from peachjam_ml.embeddings import TEXT_INJECTION_SEPARATOR
from peachjam_search.models import SearchClick


@dataclasses.dataclass
class SearchHit:
    es_hit: any
    id: int
    index: str
    score: float
    position: int
    document: CoreDocument = None
    best_match: bool = False
    highlight: dict = None
    pages: list = None
    provisions: list = None

    @classmethod
    def from_es_hits(cls, engine, es_hits):
        hits = [cls.from_es_hit(engine, es_hit, i) for i, es_hit in enumerate(es_hits)]

        # determine best match: is the first result's score significantly better than the next?
        if engine.page == 1 and len(hits) > 1 and hits[0].score / hits[1].score >= 1.2:
            hits[0].best_match = True

        return hits

    @classmethod
    def from_es_hit(cls, engine, es_hit, i):
        return SearchHit(
            es_hit=es_hit,
            id=int(es_hit.meta.id),
            index=es_hit.meta.index,
            score=es_hit.meta.score,
            position=(engine.page - 1) * engine.page_size + i + 1,
        )

    @classmethod
    def attach_documents(cls, hits, fake_documents=None):
        if fake_documents is None:
            fake_documents = settings.PEACHJAM["SEARCH_FAKE_DOCUMENTS"]
        if fake_documents:
            cls.attach_fake_documents(hits)
            return

        qs = (
            CoreDocument.objects.for_document_table()
            .filter(pk__in=[hit.id for hit in hits])
            .prefetch_related("alternative_names")
        )

        documents = {d.id: d for d in qs}
        for hit in hits:
            hit.document = documents.get(hit.id)

    @classmethod
    def attach_fake_documents(cls, hits):
        for hit in hits:
            hit.set_fake_document()

    def __post_init__(self):
        self.set_highlight()
        self.set_pages()
        self.set_provisions()

    @property
    def meta(self):
        return self.es_hit.meta

    def set_highlight(self):
        if hasattr(self.meta, "highlight"):
            self.highlight = self.meta.highlight.__dict__["_d_"]
        else:
            self.highlight = {}

        # add text content chunks as content highlights
        if (
            not self.highlight.get("content")
            and hasattr(self.meta, "inner_hits")
            and hasattr(self.meta.inner_hits, "content_chunks")
        ):
            self.highlight["content"] = []
            for chunk in self.meta.inner_hits.content_chunks.hits.hits:
                if chunk._source.type == "text":
                    self.highlight["content"].append(escape(chunk._source.text))
                    # only add one, otherwise it's too long
                    break

    def set_pages(self):
        """Serialize nested page hits and highlights."""
        self.pages = []
        if hasattr(self.meta, "inner_hits"):
            if hasattr(self.meta.inner_hits, "pages"):
                for page in self.meta.inner_hits.pages.hits.hits:
                    info = page._source.to_dict()
                    info["highlight"] = (
                        self.fix_dot_keys(page.highlight.to_dict())
                        if hasattr(page, "highlight")
                        else {}
                    )
                    info["score"] = page._score
                    self.merge_exact_highlights(info["highlight"])
                    self.pages.append(info)

            # merge in page-based content chunks
            if hasattr(self.meta.inner_hits, "content_chunks"):
                for chunk in self.meta.inner_hits.content_chunks.hits.hits:
                    if chunk._source.type == "page":
                        # max pages to return
                        if len(self.pages) >= 2:
                            break
                        info = chunk._source.to_dict()
                        page_num = info["portion"]
                        if page_num not in [p["page_num"] for p in self.pages]:
                            self.pages.append(
                                {
                                    "page_num": page_num,
                                    "highlight": {"pages.body": [escape(info["text"])]},
                                    "score": chunk._score,
                                }
                            )

    def set_provisions(self):
        """Serialize nested provision hits and highlights."""
        self.provisions = []
        # keep track of which provisions (including parents) we've seen, so that we don't, for
        # example, repeat Chapter 7 if Chapter 7, Section 32 is also a hit
        seen = set()
        if hasattr(self.meta, "inner_hits"):
            if hasattr(self.meta.inner_hits, "provisions"):
                for provision in self.meta.inner_hits.provisions.hits.hits:
                    info = provision._source.to_dict()

                    if info["id"] in seen:
                        continue
                    seen.add(info["id"])
                    seen.update(info["parent_ids"])

                    info["highlight"] = (
                        self.fix_dot_keys(provision.highlight.to_dict())
                        if hasattr(provision, "highlight")
                        else {}
                    )
                    self.merge_exact_highlights(info["highlight"])

                    info["parents"] = [
                        {"title": title, "id": id}
                        for title, id in zip(info["parent_titles"], info["parent_ids"])
                    ]

                    self.provisions.append(info)

            # merge in provision-based content chunks
            if hasattr(self.meta.inner_hits, "content_chunks"):
                for chunk in self.meta.inner_hits.content_chunks.hits.hits:
                    if chunk._source.type == "provision":
                        # max provisions to return
                        if len(self.provisions) >= 3:
                            break

                        info = chunk._source.to_dict()
                        if info["portion"] in seen:
                            continue
                        seen.add(info["portion"])
                        if info.get("parent_ids"):
                            seen.update(info["parent_ids"])
                        else:
                            info["parent_ids"] = []
                            info["parent_titles"] = []

                        text = info["text"]
                        if TEXT_INJECTION_SEPARATOR in text:
                            # remove injected text at the start
                            text = text.split(TEXT_INJECTION_SEPARATOR, 1)[1]

                        info["highlight"] = {"provisions.body": [escape(text)]}
                        info["id"] = info["portion"]
                        info["type"] = info["provision_type"]
                        self.provisions.append(info)

    def merge_exact_highlights(self, highlight):
        # fold .exact highlights into the main field to make life easier for the client
        for key, value in list(highlight.items()):
            if key.endswith(".exact"):
                short = key[:-6]
                if short not in highlight:
                    highlight[short] = value
                del highlight[key]

    def fix_dot_keys(self, d):
        """In a dictionary, replace dots in keys with underscores so that they can be referenced in a template."""
        for k, v in list(d.items()):
            if "." in k:
                d[k.replace(".", "_")] = v
        return d

    def set_fake_document(self):
        """Attaches a fake document. This is used when we know elasticsearch results won't be in a local database,
        for example with AfricanLII where it searches remote document indexes."""

        class FakeDocument:
            def __init__(self, d):
                self.d = d

            def __getattr__(self, item):
                return self.d.get(item, None)

            def get_absolute_url(self):
                return self.d.get("expression_frbr_uri", "")

        self.document = FakeDocument(self.es_hit.to_dict())

    def as_dict(self):
        return {
            field.name: getattr(self, field.name)
            for field in dataclasses.fields(self)
            if field.name not in ["es_hit"]
        }

    def raw(self):
        data = self.meta.to_dict()
        if "explanation" in data:
            del data["explanation"]
        for key, value in data.get("inner_hits", {}).items():
            # force to_dict
            data["inner_hits"][key] = value.to_dict()
        return data


class SearchClickSerializer(ModelSerializer):
    class Meta:
        model = SearchClick
        fields = ("frbr_uri", "search_trace", "portion", "position")
