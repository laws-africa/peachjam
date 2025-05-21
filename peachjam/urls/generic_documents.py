from django.urls import path

from peachjam.views import DocumentListView, DocumentNatureListView

urlpatterns = [
    path("", DocumentListView.as_view(), name="generic_document_list"),
    path("<str:nature>", DocumentNatureListView.as_view(), name="document_nature_list"),
]
