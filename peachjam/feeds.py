import datetime
import re

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed, Rss201rev2Feed

from peachjam.models import (
    Article,
    CoreDocument,
    GenericDocument,
    Judgment,
    Legislation,
)


class BaseFeed(Feed):
    model = None

    def clean_xml_text(self, text):
        """Remove control characters that are not allowed in XML."""
        return re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", text)

    def items(self):
        if self.model in [Article]:
            return self.model.objects.filter(published=True).order_by("-date")[:100]

        return self.model.objects.order_by("-created_at")[:100]

    def item_pubdate(self, item):
        return datetime.datetime.combine(item.date, datetime.time())

    def item_title(self, item):
        return self.clean_xml_text(item.title)

    def item_description(self, item):
        return self.clean_xml_text(item.title)


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

    def __call__(self, request, *args, **kwargs):
        self.request = request
        return super().__call__(request, *args, **kwargs)

    def item_extra_kwargs(self, item):
        if item.image:
            image_url = self.request.build_absolute_uri(item.image.url)
        else:
            image_url = ""

        return {
            "image": image_url,
            "body": item.body,
        }


class ArticleAtomSiteNewsFeed(ArticleFeed, BaseAtomFeed):
    subtitle = ArticleFeed.description
