from django.urls import path, re_path

from .views import SimilarDocumentsDocumentDetailView, SimilarDocumentsFolderView

urlpatterns = [
    re_path(
        r"^(?P<frbr_uri>akn/.*)/similar-documents$",
        SimilarDocumentsDocumentDetailView.as_view(),
        name="document_similar_docs",
    ),
    path(
        "user/folder/<int:pk>/similar-documents",
        SimilarDocumentsFolderView.as_view(),
        name="folder_similar_docs",
    ),
]
