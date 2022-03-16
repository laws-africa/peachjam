from rest_framework.pagination import LimitOffsetPagination
from elasticsearch_dsl import Q
from django_elasticsearch_dsl_drf.viewsets import BaseDocumentViewSet
from django_elasticsearch_dsl_drf.pagination import PageNumberPagination
from django_elasticsearch_dsl_drf.filter_backends import (
    OrderingFilterBackend,
    DefaultOrderingFilterBackend,
    SourceBackend,
    SearchFilterBackend,
    FacetedFilterSearchFilterBackend
)

from peach_jam.models import Decision
from peachjam_api.serializers import DecisionSerializer
from peachjam_api.documents import DecisionDocument

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
        'document_content': 'document_content',
    }

    search_fields = (
          'title', 
          'author',
          'country',
          'citation', 
          'matter_type',
        #   'case_number_numeric',
        #   'case_number_year', 
        #   'case_number_string', 
        #   'document_content', 
        #   'source_url', 
    )

    faceted_search_fields = {
        'author': {
            'field': 'author.name',
        },
        'country': {
            'field': 'country.name',
        },
        'matter_type': {
            'field': 'matter_type',
        },
        'year': {
            'field':'case_number_year',
        },
        'case_number': {
            'field': 'case_number_numeric'
        },
    }
