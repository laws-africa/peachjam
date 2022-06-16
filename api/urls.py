from django.urls import path

from .views import CitationLinkDetail, CitationLinkList

urlpatterns = [
    path("<int:pk>/enrichments/citation-links", CitationLinkDetail.as_view()),
    path("enrichments/citation-links", CitationLinkList.as_view()),
]
