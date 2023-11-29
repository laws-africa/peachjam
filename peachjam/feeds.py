import datetime

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed, Rss201rev2Feed

from peachjam.models import (
    Article,
    CoreDocument,
    GenericDocument,
    Judgment,
    LegalInstrument,
    Legislation,
)


class BaseFeed(Feed):
    model = None

    def items(self):
        if self.model in [Article]:
            return self.model.objects.filter(published=True).order_by("-date")[:100]

        return self.model.objects.order_by("-created_at")[:100]

    def item_pubdate(self, item):
        return datetime.datetime.combine(item.date, datetime.time())


class BaseAtomFeed(BaseFeed):
    feed_type = Atom1Feed


class JudgmentFeed(BaseFeed):
    model = Judgment
    link = "/judgments/"
    description = "Updates on changes and additions to Judgments"


class JudgmentAtomSiteNewsFeed(JudgmentFeed, BaseAtomFeed):
    subtitle = JudgmentFeed.description


class GenericDocumentFeed(BaseFeed):
    model = GenericDocument
    title = "Generic Documents"
    link = "/doc/"
    description = "Updates on changes and additions to Generic Documents"


class GenericDocumentAtomSiteNewsFeed(GenericDocumentFeed, BaseAtomFeed):
    subtitle = GenericDocumentFeed.description


class LegalInstrumentFeed(BaseFeed):
    model = LegalInstrument
    title = "Legal Instruments"
    link = "/legal_instruments/"
    description = "Updates on changes and additions to Legal Instruments"


class LegalInstrumentAtomSiteNewsFeed(LegalInstrumentFeed, BaseAtomFeed):
    subtitle = LegalInstrumentFeed.description


class LegislationFeed(BaseFeed):
    model = Legislation
    title = "Legal Instruments"
    link = "/legal_instruments/"
    description = "Updates on changes and additions to Legal Instruments"


class LegislationAtomSiteNewsFeed(LegislationFeed, BaseAtomFeed):
    subtitle = LegislationFeed.description


class CoreDocumentFeed(BaseFeed):
    model = CoreDocument
    title = "Core Documents"
    link = "/core_documents"
    description = "Updates on changes and additions to Core Documents"


class CoreDocumentAtomSiteNewsFeed(CoreDocumentFeed, BaseAtomFeed):
    subtitle = CoreDocumentFeed.description


class CustomArticleFeedGenerator(Rss201rev2Feed):
    def add_item_elements(self, handler, item):
        super().add_item_elements(handler, item)
        handler.addQuickElement("image", item.get("image", ""))
        handler.addQuickElement("body", item.get("body", ""))


class ArticleFeed(BaseFeed):
    model = Article
    title = f"{settings.PEACHJAM['APP_NAME']} Articles"
    link = "/articles/"
    description = "Updates on changes and additions to articles"
    feed_type = CustomArticleFeedGenerator

    def item_extra_kwargs(self, item):
        return {
            "image": item.image.url if item.image else "",
            "body": item.body,
        }


class ArticleAtomSiteNewsFeed(ArticleFeed, BaseAtomFeed):
    subtitle = ArticleFeed.description
