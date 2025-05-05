from django.urls import path

from peachjam.feeds import (
    ArticleAtomSiteNewsFeed,
    CoreDocumentAtomSiteNewsFeed,
    GenericDocumentAtomSiteNewsFeed,
    JudgmentAtomSiteNewsFeed,
    LegislationAtomSiteNewsFeed,
)

urlpatterns = [
    # feeds
    path("judgments.xml", JudgmentAtomSiteNewsFeed(), name="judgment_feed"),
    path(
        "generic_documents.xml",
        GenericDocumentAtomSiteNewsFeed(),
        name="generic_document_feed",
    ),
    path("legislation.xml", LegislationAtomSiteNewsFeed(), name="legislation_feed"),
    path("all.xml", CoreDocumentAtomSiteNewsFeed(), name="atom_feed"),
    path("articles.xml", ArticleAtomSiteNewsFeed(), name="article_feed"),
]
