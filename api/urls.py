from django.urls import path

from .views import CitationLinkDetail, CitationLinkList

urlpatterns = [
    path(
        "documents/<int:pk>/enrichments/citation-links",
        CitationLinkDetail.as_view(),
        name="citation_detail",
    ),
    path("", CitationLinkList.as_view(), name="citation_list"),
]
