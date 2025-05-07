from django.urls import path, re_path
from django.views.decorators.cache import cache_page

from peachjam.urls import CACHE_DURATION

from .views import SimilarDocumentsDocumentDetailView, SimilarDocumentsFolderView

urlpatterns = [
    re_path(
        r"^(?P<frbr_uri>akn/.*)/similar-documents$",
        cache_page(CACHE_DURATION)(SimilarDocumentsDocumentDetailView.as_view()),
        name="document_similar_docs",
    ),
    path(
        "folder/<int:pk>/similar-documents",
        SimilarDocumentsFolderView.as_view(),
        name="folder_similar_docs",
    ),
]
