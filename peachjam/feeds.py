import datetime
import re

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed, Rss201rev2Feed

from peachjam.models import Article


class ArticleFeed(Feed):
    title = f"{settings.PEACHJAM['APP_NAME']} Articles"
    link = "/articles/"
    description = "Updates on changes and additions to articles"

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

    def clean_xml_text(self, text):
        """Remove control characters that are not allowed in XML."""
        return re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", text)

    def items(self):
        return Article.objects.filter(published=True).order_by("-date")[:100]

    def item_pubdate(self, item):
        return datetime.datetime.combine(item.date, datetime.time())

    def item_title(self, item):
        return self.clean_xml_text(item.title)

    def item_description(self, item):
        return self.clean_xml_text(item.title)


class CustomArticleFeedGenerator(Rss201rev2Feed):
    def add_item_elements(self, handler, item):
        super().add_item_elements(handler, item)
        handler.addQuickElement("image", item.get("image", ""))
        handler.addQuickElement("body", item.get("body", ""))


class ArticleRSSFeed(ArticleFeed):
    feed_type = CustomArticleFeedGenerator


class ArticleAtomSiteNewsFeed(ArticleFeed):
    feed_type = Atom1Feed
    subtitle = ArticleFeed.description
