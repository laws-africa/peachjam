from collections import defaultdict

from cobalt.uri import FrbrUri
from django.utils.html import strip_tags
from elasticsearch_dsl import Search
from elasticsearch_dsl.query import Bool
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from peachjam.models import Judgment
from peachjam_ml.embeddings import TEXT_INJECTION_SEPARATOR
from peachjam_search.engine import PortionSearchEngine
from peachjam_search.serializers import (
    PortionContent,
    PortionHit,
    PortionMetadata,
    PortionSearchRequestSerializer,
    PortionSearchResponseSerializer,
    PortionType,
)


class PortionSearchPermission(BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm("peachjam_search.can_search_portions")


class PortionSearchView(APIView):
    permission_classes = [PortionSearchPermission]
    engine = None

    def post(self, request, *args, **kwargs):
        serializer = PortionSearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        input_data = serializer.validated_data

        self.engine = PortionSearchEngine()
        self.engine.query = input_data["text"]
        self.engine.knn_k = (
            input_data["top_k"] * 10
        )  # retrieve more to allow for combining chunks

        self.engine.filters = []
        if input_data.get("pre_filters", None):
            self.engine.filters.append(input_data["pre_filters"])
        if input_data.get("filters", None):
            self.engine.filters.append(input_data["filters"])

        es_response = self.engine.execute()

        portions = self.build_portions(es_response, request)
        portions = portions[: input_data["top_k"]]

        return Response(PortionSearchResponseSerializer({"results": portions}).data)

    def build_portions(self, es_response, request):
        portions = []
        # (expression_frbr_uri, portion_id) tuples we've seen, for deduplication
        seen = set()
        # a list of portion ids to load full text for
        provisions_to_load = defaultdict(list)
        pages_to_load = defaultdict(list)
        summaries_to_load = []

        for hit in es_response.hits.hits:
            expression_frbr_uri = hit._source.expression_frbr_uri
            frbr_uri = FrbrUri.parse(expression_frbr_uri)
            common_metadata = {
                "work_frbr_uri": frbr_uri.work_uri(),
                "frbr_place": frbr_uri.place,
                "frbr_country": frbr_uri.country,
                "frbr_doctype": frbr_uri.doctype,
                "frbr_subtype": frbr_uri.subtype,
                "title": hit._source.title,
                "expression_date": frbr_uri.expression_date[1:],
                "expression_frbr_uri": expression_frbr_uri,
                "repealed": getattr(hit._source, "repealed", None),
                "commenced": getattr(hit._source, "commenced", None),
                "principal": getattr(hit._source, "principal", None),
                "public_url": self.request.build_absolute_uri(expression_frbr_uri),
            }

            if frbr_uri.doctype == "judgment":
                summaries_to_load.append(expression_frbr_uri)
                judgment_metadata = {
                    **common_metadata,
                    # use the source, because a parsed FRBR URI is ambiguous if there is an actor
                    "frbr_subtype": hit._source.frbr_uri_subtype,
                    # TODO: enable once data is backfilled in ES
                    # "frbr_actor": hit._source.frbr_uri_actor,
                    "flynote": getattr(hit._source, "flynote", None),
                    "blurb": getattr(hit._source, "blurb", None),
                }

                # we only return summaries for judgments
                portions.append(
                    self.make_portion_hit(
                        common_metadata=judgment_metadata,
                        score=1 - hit._score,
                        # this will be filled in later
                        text="",
                        portion_type=PortionType.SUMMARY,
                    )
                )
                continue

            if hasattr(hit, "inner_hits") and hasattr(hit.inner_hits, "content_chunks"):
                for chunk in hit.inner_hits.content_chunks.hits.hits:
                    if chunk._source.portion:
                        if chunk._source.type == "provision":
                            provisions_to_load[frbr_uri].append(chunk._source.portion)
                        elif (
                            chunk._source.type == "page" and chunk._source.n_chunks > 1
                        ):
                            pages_to_load[frbr_uri].append(chunk._source.portion)

                    portion_id = getattr(chunk._source, "portion", None)
                    if (expression_frbr_uri, portion_id) in seen:
                        continue
                    seen.add((expression_frbr_uri, portion_id))

                    item = self.make_portion_hit(
                        common_metadata=common_metadata,
                        # retriever-based scores are always [0, 1]
                        score=1 - chunk._score,
                        text=self.clean_text(chunk._source.text),
                        portion_type=chunk._source.type,
                        portion_id=portion_id,
                        portion_public_url=self.portion_public_url(
                            request, expression_frbr_uri, chunk._source.type, portion_id
                        ),
                    )
                    portions.append(item)

            elif hasattr(hit, "inner_hits") and hasattr(hit.inner_hits, "provisions"):
                for provision in hit.inner_hits.provisions.hits.hits:
                    portion_id = getattr(provision._source, "id", None)
                    if portion_id:
                        provisions_to_load[frbr_uri].append(portion_id)

                    if (expression_frbr_uri, portion_id) in seen:
                        continue
                    seen.add((expression_frbr_uri, portion_id))

                    text = ""
                    if hasattr(provision, "highlight"):
                        highlight = provision.highlight.to_dict()
                        body = (
                            highlight.get("provisions.body")
                            or highlight.get("provisions.body.exact")
                            or []
                        )
                        if body:
                            text = strip_tags(body[0])

                    item = self.make_portion_hit(
                        common_metadata=common_metadata,
                        # retriever-based scores are always [0, 1]
                        score=(
                            provision._score
                            if self.engine.mode == "text"
                            else 1 - provision._score
                        ),
                        text=text,
                        portion_type=PortionType.PROVISION,
                        portion_id=portion_id,
                        portion_title=getattr(provision._source, "title", None),
                        portion_parent_ids=list(
                            getattr(provision._source, "parent_ids", []) or []
                        ),
                        portion_parent_titles=list(
                            getattr(provision._source, "parent_titles", []) or []
                        ),
                        portion_public_url=self.portion_public_url(
                            request,
                            expression_frbr_uri,
                            PortionType.PROVISION,
                            portion_id,
                        ),
                    )
                    portions.append(item)

            elif hasattr(hit, "inner_hits") and hasattr(hit.inner_hits, "pages"):
                for page in hit.inner_hits.pages.hits.hits:
                    page_num = getattr(page._source, "page_num", None)
                    if page_num is not None:
                        pages_to_load[frbr_uri].append(page_num)

                    portion_id = str(page_num) if page_num is not None else None
                    if (expression_frbr_uri, portion_id) in seen:
                        continue
                    seen.add((expression_frbr_uri, portion_id))

                    text = ""
                    if hasattr(page, "highlight"):
                        highlight = page.highlight.to_dict()
                        body = (
                            highlight.get("pages.body")
                            or highlight.get("pages.body.exact")
                            or []
                        )
                        if body:
                            text = strip_tags(body[0])

                    item = self.make_portion_hit(
                        common_metadata=common_metadata,
                        # retriever-based scores are always [0, 1]
                        score=(
                            page._score
                            if self.engine.mode == "text"
                            else 1 - page._score
                        ),
                        text=text,
                        portion_type=PortionType.PAGE,
                        portion_id=portion_id,
                        portion_public_url=self.portion_public_url(
                            request, expression_frbr_uri, PortionType.PAGE, portion_id
                        ),
                    )
                    portions.append(item)

        self.load_portion_details(
            portions, provisions_to_load, pages_to_load, summaries_to_load
        )

        portions.sort(key=lambda x: x.score)

        return portions

    def clean_text(self, text):
        # strip the additional context, if present
        return text.split(TEXT_INJECTION_SEPARATOR, 1)[-1]

    def make_portion_hit(
        self,
        common_metadata,
        score,
        text,
        portion_type,
        portion_id=None,
        portion_title=None,
        portion_parent_ids=None,
        portion_parent_titles=None,
        portion_public_url=None,
    ):
        return PortionHit(
            score=score,
            content=PortionContent(text=text),
            metadata=PortionMetadata(
                **common_metadata,
                portion_type=portion_type,
                portion_id=portion_id,
                portion_title=portion_title,
                portion_parent_ids=portion_parent_ids,
                portion_parent_titles=portion_parent_titles,
                portion_public_url=portion_public_url,
            ),
        )

    def portion_public_url(
        self, request, expression_frbr_uri, portion_type, portion_id
    ):
        if portion_id is not None:
            if portion_type == "page":
                return request.build_absolute_uri(
                    f"{expression_frbr_uri}#page-{portion_id}"
                )
            elif portion_type == "provision":
                return request.build_absolute_uri(f"{expression_frbr_uri}#{portion_id}")

    def load_portion_details(
        self, portions, provisions_to_load, pages_to_load, summaries_to_load
    ):
        """Load additional details for portions. This includes titles for provisions, and full text for portions that
        have multiple chunks. We do this by querying Elasticsearch again, using the "provisions" and "pages" nested
        fields."""

        search = Search(using=self.engine.client, index=self.engine.index)
        search = search.source(["expression_frbr_uri"])
        provision_filters = [
            [
                {"term": {"expression_frbr_uri": frbr_uri.expression_uri()}},
                {
                    "nested": {
                        "path": "provisions",
                        "query": {
                            "terms": {"provisions.id": portion_ids},
                        },
                        "inner_hits": {
                            "name": f"provisions_{frbr_uri.expression_uri()}",
                            "size": 100,
                            "_source": {
                                "includes": [
                                    "provisions.body",
                                    "provisions.id",
                                    "provisions.title",
                                    "provisions.parent_ids",
                                    "provisions.parent_titles",
                                ]
                            },
                        },
                    }
                },
            ]
            for frbr_uri, portion_ids in provisions_to_load.items()
        ]
        page_filters = [
            [
                {"term": {"expression_frbr_uri": frbr_uri.expression_uri()}},
                {
                    "nested": {
                        "path": "pages",
                        "query": {
                            "terms": {"pages.page_num": page_nums},
                        },
                        "inner_hits": {
                            "name": f"pages_{frbr_uri.expression_uri()}",
                            "size": 100,
                            "_source": {"includes": ["pages.body", "pages.page_num"]},
                        },
                    }
                },
            ]
            for frbr_uri, page_nums in pages_to_load.items()
        ]
        filters = provision_filters + page_filters

        if filters:
            search = search.query(Bool(should=[Bool(filter=f) for f in filters]))
            es_response = search.execute()

            # build up a lookup dict
            portion_details = {}
            for hit in es_response.hits.hits:
                for inner_hit_key in hit.inner_hits:
                    inner_hit = hit.inner_hits[inner_hit_key]
                    for portion in inner_hit.hits.hits:
                        if hasattr(portion._source, "id"):
                            # provision
                            portion_id = portion._source.id
                        else:
                            # page - key in portion_details will be a string
                            portion_id = str(portion._source.page_num)
                        key = (hit._source.expression_frbr_uri, portion_id)
                        portion_details[key] = portion._source

            # update portions
            for portion in portions:
                key = (
                    portion.metadata.expression_frbr_uri,
                    portion.metadata.portion_id,
                )
                if key in portion_details:
                    details = portion_details[key]
                    if hasattr(details, "title"):
                        portion.metadata.portion_title = details.title
                    if getattr(details, "parent_ids", None):
                        portion.metadata.portion_parent_ids = list(details.parent_ids)
                    if getattr(details, "parent_titles", None):
                        portion.metadata.portion_parent_titles = list(
                            details.parent_titles
                        )
                    if hasattr(details, "body"):
                        portion.content.text = details.body

        # Load summaries for judgments
        if summaries_to_load:
            summaries = {
                j.expression_frbr_uri: j
                for j in Judgment.objects.filter(
                    expression_frbr_uri__in=summaries_to_load
                ).only("expression_frbr_uri", "case_summary", "issues", "held")
            }

            for portion in portions:
                if portion.metadata.portion_type == PortionType.SUMMARY:
                    judgment = summaries.get(portion.metadata.expression_frbr_uri)
                    if judgment:
                        summary_parts = []
                        if judgment.case_summary:
                            summary_parts.append(judgment.case_summary)
                        if judgment.issues:
                            summary_parts.append(
                                "Issues:\n"
                                + "\n".join(f"- {x}" for x in judgment.issues)
                            )
                        if judgment.held:
                            summary_parts.append(
                                "Held:\n" + "\n".join(f"- {x}" for x in judgment.held)
                            )
                        portion.content.text = "\n\n".join(summary_parts)
