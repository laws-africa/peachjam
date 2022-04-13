from django.views.generic import TemplateView
from django_elasticsearch_dsl_drf.filter_backends import (
    DefaultOrderingFilterBackend,
    FacetedFilterSearchFilterBackend,
    OrderingFilterBackend,
    SearchFilterBackend,
    SourceBackend,
)
from django_elasticsearch_dsl_drf.viewsets import BaseDocumentViewSet
from elasticsearch_dsl import DateHistogramFacet

from peachjam.views import AuthedViewMixin
from peachjam_search.documents import JudgmentDocument
from peachjam_search.serializers import JudgmentSerializer


class SearchView(AuthedViewMixin, TemplateView):
    template_name = "peachjam_search/search.html"


class JudgmentSearchViewSet(BaseDocumentViewSet):
    """
    API endpoint that allows judgments to be searched.
    """

    document = JudgmentDocument
    serializer_class = JudgmentSerializer
    filter_backends = [
        OrderingFilterBackend,
        DefaultOrderingFilterBackend,
        SearchFilterBackend,
        FacetedFilterSearchFilterBackend,
        SourceBackend,
    ]

    ordering_fields = {"date": "_date", "title": "title"}

    filter_fields = {
        "title": "title",
        "citation": "citation",
        "author": "author",
        "country": "country",
        "matter_type": "matter_type",
    }

    search_fields = (
        "title",
        "author",
        "country",
        "citation",
        "matter_type",
        "document_content",
    )

    faceted_search_fields = {
        "author": {
            "field": "author",
        },
        "country": {
            "field": "country",
        },
        "matter_type": {
            "field": "matter_type",
        },
        "date": {
            "field": "date",
            "facet": DateHistogramFacet,
            "options": {"interval": "year"},
        },
    }
