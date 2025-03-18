from django.utils.html import escape
from django.utils.translation import get_language_from_request
from rest_framework.serializers import (
    BooleanField,
    CharField,
    FloatField,
    IntegerField,
    ListField,
    ListSerializer,
    ModelSerializer,
    Serializer,
    SerializerMethodField,
)

from peachjam.models import DocumentTopic
from peachjam_search.embeddings import TEXT_INJECTION_SEPARATOR
from peachjam_search.models import SearchClick


class SearchableDocumentListSerializer(ListSerializer):
    def to_representation(self, data):
        self.add_topic_path_names(data)
        return super().to_representation(data)

    def add_topic_path_names(self, data):
        # add topic path names for topics that should be shown in result listings
        doc_ids = [doc.meta.id for doc in data]
        doc_topics = DocumentTopic.objects.filter(
            document_id__in=doc_ids, topic__show_in_document_listing=True
        ).prefetch_related("topic")
        topics = {}
        for doc_topic in doc_topics:
            topics.setdefault(str(doc_topic.document_id), []).append(
                doc_topic.topic.path_name
            )

        for hit in data:
            hit.topic_path_names = topics.get(hit.meta.id, [])


class SearchableDocumentSerializer(Serializer):
    id = CharField(source="meta.id")
    doc_type = CharField()
    title = CharField()
    date = CharField()
    year = IntegerField()
    jurisdiction = CharField()
    locality = CharField()
    citation = CharField()
    expression_frbr_uri = CharField()
    work_frbr_uri = CharField()
    authors = ListField()
    matter_type = CharField()
    created_at = CharField()
    case_number = ListField()
    judges = ListField()
    is_most_recent = BooleanField()
    alternative_names = ListField()
    labels = ListField()
    topic_path_names = ListField()
    _score = FloatField(source="meta.score")
    _index = CharField(source="meta.index")

    nature = SerializerMethodField()
    court = SerializerMethodField()
    highlight = SerializerMethodField()
    pages = SerializerMethodField()
    provisions = SerializerMethodField()
    outcome = SerializerMethodField()
    registry = SerializerMethodField()
    explanation = SerializerMethodField()
    raw = SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.language_suffix = ""
        if "request" in self.context:
            self.language_suffix = "_" + get_language_from_request(
                self.context["request"]
            )

    class Meta:
        list_serializer_class = SearchableDocumentListSerializer

    def get_highlight(self, obj):
        highlight = {}
        if hasattr(obj.meta, "highlight"):
            highlight = obj.meta.highlight.__dict__["_d_"]

        # add text content chunks as content highlights
        if (
            not highlight.get("content")
            and hasattr(obj.meta, "inner_hits")
            and hasattr(obj.meta.inner_hits, "content_chunks")
        ):
            highlight["content"] = []
            for chunk in obj.meta.inner_hits.content_chunks.hits.hits:
                if chunk._source.type == "text":
                    highlight["content"].append(escape(chunk._source.text))
                    # only add one, otherwise it's too long
                    break

        return highlight

    def get_pages(self, obj):
        """Serialize nested page hits and highlights."""
        pages = []
        if hasattr(obj.meta, "inner_hits"):
            if hasattr(obj.meta.inner_hits, "pages"):
                for page in obj.meta.inner_hits.pages.hits.hits:
                    info = page._source.to_dict()
                    info["highlight"] = (
                        page.highlight.to_dict() if hasattr(page, "highlight") else {}
                    )
                    info["score"] = page._score
                    self.merge_exact_highlights(info["highlight"])
                    pages.append(info)

            # merge in page-based content chunks
            if hasattr(obj.meta.inner_hits, "content_chunks"):
                for chunk in obj.meta.inner_hits.content_chunks.hits.hits:
                    if chunk._source.type == "page":
                        # max pages to return
                        if len(pages) >= 2:
                            break
                        info = chunk._source.to_dict()
                        page_num = info["portion"]
                        if page_num not in [p["page_num"] for p in pages]:
                            pages.append(
                                {
                                    "page_num": page_num,
                                    "highlight": {"pages.body": [escape(info["text"])]},
                                    "score": chunk._score,
                                }
                            )

        return pages

    def get_provisions(self, obj):
        """Serialize nested provision hits and highlights."""
        provisions = []
        # keep track of which provisions (including parents) we've seen, so that we don't, for
        # example, repeat Chapter 7 if Chapter 7, Section 32 is also a hit
        seen = set()
        if hasattr(obj.meta, "inner_hits"):
            if hasattr(obj.meta.inner_hits, "provisions"):
                for provision in obj.meta.inner_hits.provisions.hits.hits:
                    info = provision._source.to_dict()

                    if info["id"] in seen:
                        continue
                    seen.add(info["id"])
                    seen.update(info["parent_ids"])

                    info["highlight"] = (
                        provision.highlight.to_dict()
                        if hasattr(provision, "highlight")
                        else {}
                    )
                    self.merge_exact_highlights(info["highlight"])
                    provisions.append(info)

            # merge in provision-based content chunks
            if hasattr(obj.meta.inner_hits, "content_chunks"):
                for chunk in obj.meta.inner_hits.content_chunks.hits.hits:
                    if chunk._source.type == "provision":
                        # max provisions to return
                        if len(provisions) >= 3:
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
                        provisions.append(info)

        return provisions

    def get_court(self, obj):
        return obj["court" + self.language_suffix]

    def get_nature(self, obj):
        return obj["nature" + self.language_suffix]

    def get_outcome(self, obj):
        if hasattr(obj, "outcome" + self.language_suffix):
            val = obj["outcome" + self.language_suffix]
            if val is not None:
                val = list(val)
            return val
        return None

    def get_registry(self, obj):
        return obj["registry" + self.language_suffix]

    def merge_exact_highlights(self, highlight):
        # fold .exact highlights into the main field to make life easier for the client
        for key, value in list(highlight.items()):
            if key.endswith(".exact"):
                short = key[:-6]
                if short not in highlight:
                    highlight[short] = value
                del highlight[key]

    def get_explanation(self, obj):
        if self.context.get("explain"):
            if hasattr(obj.meta, "explanation"):
                return obj.meta.explanation.to_dict()

    def get_raw(self, obj):
        if self.context.get("explain"):
            data = obj.meta.to_dict()
            del data["explanation"]
            for key, value in data.get("inner_hits", {}).items():
                # force to_dict
                data["inner_hits"][key] = value.to_dict()
            return data


class SearchClickSerializer(ModelSerializer):
    class Meta:
        model = SearchClick
        fields = ("frbr_uri", "search_trace", "portion", "position")
