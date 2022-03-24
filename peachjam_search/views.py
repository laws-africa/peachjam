from rest_framework.pagination import LimitOffsetPagination
from elasticsearch_dsl import DateHistogramFacet
from django_elasticsearch_dsl_drf.viewsets import BaseDocumentViewSet
from django_elasticsearch_dsl_drf.pagination import PageNumberPagination
from django_elasticsearch_dsl_drf.filter_backends import (
    OrderingFilterBackend,
    DefaultOrderingFilterBackend,
    SourceBackend,
    SearchFilterBackend,
    FacetedFilterSearchFilterBackend
)

from peachjam.models import Decision
from peachjam_search.serializers import DecisionSerializer
from peachjam_search.documents import DecisionDocument

class DecisionSearchViewSet(BaseDocumentViewSet):
    """
    API endpoint that allows decisions to be searched.
    """
    document = DecisionDocument
    serializer_class = DecisionSerializer
    filter_backends = [
        OrderingFilterBackend,
        DefaultOrderingFilterBackend,
        SearchFilterBackend,
        FacetedFilterSearchFilterBackend,
        SourceBackend,
    ]

    ordering_fields = {
        'date': '_date',
        'title': 'title'
    }

    filter_fields = {
        'title': 'title',
        'citation': 'citation',
        'author': 'author',
        'country': 'country',
        'matter_type': 'matter_type',
    }

    search_fields = (
          'title', 
          'author',
          'country',
          'citation', 
          'matter_type',
          'document_content', 
    )

    faceted_search_fields = {
        'author': {
            'field': 'author',
        },
        'country': {
            'field': 'country',
        },
        'matter_type': {
            'field': 'matter_type',
        },
        'date': {
            'field': 'date',
            'facet': DateHistogramFacet,
            'options': {
                'interval': 'year'
            }
        },
    }
