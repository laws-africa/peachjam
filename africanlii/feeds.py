import datetime

from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed

from africanlii.models import GenericDocument, Judgment, LegalInstrument, Legislation


class JudgmentFeed(Feed):
    title = "Judgments"
    link = "/judgments/"
    description = "Updates on changes and additions to Judgments"

    def items(self):
        return Judgment.objects.order_by("-created_at")[:100]

    def item_pubdate(self, item):
        return datetime.datetime.combine(item.date, datetime.time())


class JudgmentAtomSiteNewsFeed(JudgmentFeed):
    feed_type = Atom1Feed
    subtitle = JudgmentFeed.description


class GenericDocumentFeed(Feed):
    title = "Generic Documents"
    link = "/generic_documents/"
    description = "Updates on changes and additions to Generic Documents"

    def items(self):
        return GenericDocument.objects.order_by("-created_at")[:100]

    def item_pubdate(self, item):
        return datetime.datetime.combine(item.date, datetime.time())


class GenericDocumentAtomSiteNewsFeed(GenericDocumentFeed):
    feed_type = Atom1Feed
    subtitle = GenericDocumentFeed.description


class LegalInstrumentFeed(Feed):
    title = "Legal Instruments"
    link = "/legal_instruments/"
    description = "Updates on changes and additions to Legal Instruments"

    def items(self):
        return LegalInstrument.objects.order_by("-created_at")[:100]

    def item_pubdate(self, item):
        return datetime.datetime.combine(item.date, datetime.time())


class LegalInstrumentAtomSiteNewsFeed(LegalInstrumentFeed):
    feed_type = Atom1Feed
    subtitle = LegalInstrumentFeed.description


class LegislationFeed(Feed):
    title = "Legal Instruments"
    link = "/legal_instruments/"
    description = "Updates on changes and additions to Legal Instruments"

    def items(self):
        return Legislation.objects.order_by("-created_at")[:100]

    def item_pubdate(self, item):
        return datetime.datetime.combine(item.date, datetime.time())


class LegislationAtomSiteNewsFeed(LegislationFeed):
    feed_type = Atom1Feed
    subtitle = LegislationFeed.description
