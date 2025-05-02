from django.urls import path
from django.views.decorators.cache import cache_page

from peachjam.urls import CACHE_DURATION

from .views import SimilarDocumentsView

urlpatterns = [
    path(
        "similar-documents",
        cache_page(CACHE_DURATION)(SimilarDocumentsView.as_view()),
        name="similar_documents",
    ),
]
