from collections import defaultdict

from cobalt.uri import FrbrUri
from elasticsearch_dsl import Search
from elasticsearch_dsl.query import Bool
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from peachjam_ml.embeddings import TEXT_INJECTION_SEPARATOR
from peachjam_search.engine import PortionSearchEngine
from peachjam_search.serializers import (
    PortionContent,
    PortionHit,
    PortionMetadata,
    PortionSearchRequestSerializer,
    PortionSearchResponseSerializer,
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
        # a list of portion ids to load full text for
        provisions_to_load = defaultdict(list)
        pages_to_load = defaultdict(list)

        for hit in es_response.hits.hits:
            expression_frbr_uri = hit._source.expression_frbr_uri
            frbr_uri = FrbrUri.parse(expression_frbr_uri)

            # TODO: merge in "provisions.hits"

            for chunk in hit.inner_hits.content_chunks.hits.hits:
                if chunk._source.portion:
                    if chunk._source.type == "provision":
                        provisions_to_load[frbr_uri].append(chunk._source.portion)
                    elif chunk._source.type == "page" and chunk._source.n_chunks > 1:
                        pages_to_load[frbr_uri].append(chunk._source.portion)

                portion_id = getattr(chunk._source, "portion", None)

                item = PortionHit(
                    content=PortionContent(text=self.clean_text(chunk._source.text)),
                    metadata=PortionMetadata(
                        work_frbr_uri=frbr_uri.work_uri(),
                        frbr_place=frbr_uri.place,
                        frbr_country=frbr_uri.country,
                        frbr_doctype=frbr_uri.doctype,
                        frbr_subtype=frbr_uri.subtype,
                        title=hit._source.title,
                        expression_date=frbr_uri.expression_date[1:],
                        expression_frbr_uri=expression_frbr_uri,
                        repealed=getattr(hit._source, "repealed", None),
                        commenced=getattr(hit._source, "commenced", None),
                        principal=getattr(hit._source, "principal", None),
                        public_url=self.request.build_absolute_uri(expression_frbr_uri),
                        portion_type=chunk._source.type,
                        portion_id=portion_id,
                        portion_title=None,
                        portion_public_url=self.portion_public_url(
                            request, expression_frbr_uri, chunk._source.type, portion_id
                        ),
                    ),
                    score=1 - chunk._score,
                )
                portions.append(item)

        self.load_portion_details(portions, provisions_to_load, pages_to_load)

        portions.sort(key=lambda x: x.score)

        return portions

    def clean_text(self, text):
        # strip the additional context, if present
        return text.split(TEXT_INJECTION_SEPARATOR, 1)[-1]

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

    def load_portion_details(self, portions, provisions_to_load, pages_to_load):
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
                            "name": f"provisions_{frbr_uri.expression_uri()}",
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
                    if hasattr(details, "body"):
                        portion.content.text = details.body
