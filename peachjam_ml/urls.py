from django.urls import re_path
from django.views.decorators.cache import cache_page

from peachjam.urls import CACHE_DURATION

from .views import SimilarDocumentsView

urlpatterns = [
    re_path(
        r"^(?P<frbr_uri>akn/.*)/similar-documents$",
        cache_page(CACHE_DURATION)(SimilarDocumentsView.as_view()),
        name="document_similar_docs",
    ),
]
