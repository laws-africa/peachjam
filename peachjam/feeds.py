import datetime

from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed

from peachjam.models import (
    CoreDocument,
    GenericDocument,
    Judgment,
    LegalInstrument,
    Legislation,
)


class BaseFeed(Feed):

    model = None

    def items(self):
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
    link = "/generic_documents/"
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
