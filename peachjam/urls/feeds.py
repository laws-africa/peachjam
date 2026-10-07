from django.urls import path

from peachjam.feeds import ArticleAtomSiteNewsFeed

urlpatterns = [
    # feeds
    path("articles.xml", ArticleAtomSiteNewsFeed(), name="article_feed"),
]
