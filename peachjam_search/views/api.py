from collections import defaultdict

from cobalt.uri import FrbrUri
from elasticsearch_dsl import Search
from elasticsearch_dsl.query import Bool
from rest_framework.response import Response
from rest_framework.views import APIView

from peachjam_ml.embeddings import TEXT_INJECTION_SEPARATOR
from peachjam_search.engine import RetrieverSearch, SearchEngine
from peachjam_search.serializers import (
    PortionContent,
    PortionHit,
    PortionMetadata,
    PortionSearchRequestSerializer,
    PortionSearchResponseSerializer,
)


class PortionSearchView(APIView):
    # TODO: perms
    permission_classes = []
    engine = None

    def post(self, request, *args, **kwargs):
        serializer = PortionSearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        input_data = serializer.validated_data

        self.engine = SearchEngine()
        self.engine.query = input_data["text"]
        self.engine.mode = "hybrid"

        search = RetrieverSearch(using=self.engine.client, index=self.engine.index)
        search = search.source(
            ["title", "expression_frbr_uri", "repealed", "commenced", "principal"]
        )
        search = self.engine.add_query(search)
        search = self.engine.add_sort(search)
        if input_data.get("filters"):
            search = search.query(Bool(filter=input_data["filters"].to_es_query()))
        search = self.engine.add_retrievers(search)

        es_response = search.execute()
        portions = self.build_portions(es_response)

        portions.sort(key=lambda x: x.score)
        portions = portions[: input_data["top_k"]]

        return Response(PortionSearchResponseSerializer({"results": portions}).data)

    def build_portions(self, es_response):
        portions = []
        # a list of portion ids to load full text for
        portions_to_load = defaultdict(list)

        for hit in es_response.hits.hits:
            frbr_uri = FrbrUri.parse(hit._source.expression_frbr_uri)

            # TODO: merge in "provisions.hits"

            for chunk in hit.inner_hits.content_chunks.hits.hits:
                # if there's no portion, then it means the full text, and we just have to use what's here
                if chunk._source.n_chunks > 1 and chunk._source.portion:
                    portions_to_load[frbr_uri].append(chunk._source.portion)

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
                        expression_frbr_uri=hit._source.expression_frbr_uri,
                        portion_type=chunk._source.type,
                        portion_id=getattr(chunk._source, "portion", None),
                        repealed=getattr(hit._source, "repealed", None),
                        commenced=getattr(hit._source, "commenced", None),
                        principal=getattr(hit._source, "principal", None),
                    ),
                    score=1 - chunk._score,
                )
                portions.append(item)

        if portions_to_load:
            self.load_full_portion_text(portions, portions_to_load)

        return portions

    def clean_text(self, text):
        # strip the additional context, if present
        return text.split(TEXT_INJECTION_SEPARATOR, 1)[-1]

    def load_full_portion_text(self, portions, portions_to_load):
        """Load the full text for portions that have multiple chunks. We do this by querying Elasticsearch again,
        using the "provisions" and "pages" nested fields."""

        # TODO: handle pages
        search = Search(using=self.engine.client, index=self.engine.index)
        search = search.source(["expression_frbr_uri"])
        # write an elasticsearch query to get the full text for the portions
        filters = [
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
                                "includes": ["provisions.body", "provisions.id"]
                            },
                        },
                    }
                },
            ]
            for frbr_uri, portion_ids in portions_to_load.items()
        ]

        search = search.query(Bool(should=[Bool(filter=f) for f in filters]))
        es_response = search.execute()

        # build up a lookup dict
        full_texts = {}
        for hit in es_response.hits.hits:
            for inner_hit_key in hit.inner_hits:
                inner_hit = hit.inner_hits[inner_hit_key]
                for provision in inner_hit.hits.hits:
                    portion_id = provision._source.id
                    key = (hit._source.expression_frbr_uri, portion_id)
                    full_texts[key] = provision._source.body

        # update portions with full text
        for portion in portions:
            key = (portion.metadata.expression_frbr_uri, portion.metadata.portion_id)
            if key in full_texts:
                portion.content.text = full_texts[key]
