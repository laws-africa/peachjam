import logging
from collections import OrderedDict
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _
from django.utils.translation import ngettext, override
from templated_email import send_templated_mail

from peachjam.models import ProvisionCitation, TimelineEvent
from peachjam.tasks import send_timeline_digest_email_alert

log = logging.getLogger(__name__)


class TimelineEmailService:
    MAX_ENTRIES_PER_CATEGORY = 10
    MAX_SUMMARY_ENTRIES = 5
    SUBJECT_ENTITY_MAX_LENGTH = 500
    PREHEADER_MAX_LENGTH = 90

    @staticmethod
    def already_sent_digest_within_last_24_hours(user):
        return TimelineEvent.objects.filter(
            email_alert_sent_at__gte=timezone.now() - timedelta(hours=24),
            user_following__user=user,
        ).exists()

    @staticmethod
    def is_delivery_day(today=None):
        """Return whether digests should be delivered on this site-local day."""
        today = today or timezone.localdate()
        return today.weekday() < 5

    @classmethod
    def is_digest_due(cls, user, today=None):
        today = today or timezone.localdate()
        frequency = user.userprofile.email_alert_frequency

        if frequency == user.userprofile.EmailAlertFrequency.NONE:
            return False
        if not cls.is_delivery_day(today):
            return False
        if frequency == user.userprofile.EmailAlertFrequency.DAILY:
            return True
        if frequency == user.userprofile.EmailAlertFrequency.WEEKLY:
            return today.weekday() == 0
        if frequency == user.userprofile.EmailAlertFrequency.MONTHLY:
            first_weekday = today.replace(day=1)
            while first_weekday.weekday() >= 5:
                first_weekday += timedelta(days=1)
            return today == first_weekday
        return False

    @staticmethod
    def pending_events():
        return (
            TimelineEvent.objects.filter(
                email_alert_sent_at__isnull=True,
                user_following__subscription_locked_at__isnull=True,
            )
            .filter(
                Q(user_following__saved_document__isnull=True)
                | Q(user_following__saved_document__subscription_locked_at__isnull=True)
            )
            .filter(
                Q(user_following__saved_search__isnull=True)
                | Q(user_following__saved_search__subscription_locked_at__isnull=True)
            )
        )

    @classmethod
    def send_email_alerts(cls):
        if not settings.PEACHJAM["EMAIL_ALERTS_ENABLED"] or not cls.is_delivery_day():
            return

        user_ids = (
            cls.pending_events()
            .values_list("user_following__user_id", flat=True)
            .distinct()
        )
        for user_id in user_ids:
            send_timeline_digest_email_alert(user_id)

    @classmethod
    def get_user_events(cls, user):
        return list(
            TimelineEvent.objects.prefetch_subject_documents(user)
            .filter(pk__in=cls.pending_events().filter(user_following__user=user))
            .select_related(
                "user_following",
                "user_following__saved_document",
                "user_following__saved_document__work",
                "user_following__saved_search",
            )
        )

    @staticmethod
    def last_digest_sent_at(user):
        return (
            TimelineEvent.objects.filter(
                user_following__user=user,
                email_alert_sent_at__isnull=False,
            )
            .order_by("-email_alert_sent_at")
            .values_list("email_alert_sent_at", flat=True)
            .first()
        )

    @classmethod
    def limit_documents(cls, events):
        documents = []
        has_more = False
        for event in events:
            for document in event.subject_documents:
                if len(documents) < cls.MAX_ENTRIES_PER_CATEGORY:
                    documents.append(document)
                else:
                    has_more = True
        return documents, has_more

    @staticmethod
    def document_kind(documents, count):
        """Return a reader-facing document type when the documents are uniform."""
        if documents and all(document.doc_type == "judgment" for document in documents):
            return ngettext("judgment", "judgments", count)
        return ngettext("document", "documents", count)

    @classmethod
    def followed_documents_heading(cls, followed_object, documents, count):
        return ngettext(
            "%(count)d new %(document_kind)s for %(followed_object)s",
            "%(count)d new %(document_kind)s for %(followed_object)s",
            count,
        ) % {
            "count": count,
            "document_kind": cls.document_kind(documents, count),
            "followed_object": followed_object,
        }

    @classmethod
    def followed_documents_summary_label(cls, followed_object, documents, count):
        return cls.followed_documents_heading(followed_object, documents, count)

    @classmethod
    def followed_documents_preheader_label(cls, followed_object, documents, count):
        return ngettext(
            "%(count)d %(followed_object)s %(document_kind)s",
            "%(count)d %(followed_object)s %(document_kind)s",
            count,
        ) % {
            "count": count,
            "followed_object": followed_object,
            "document_kind": cls.document_kind(documents, count),
        }

    @staticmethod
    def saved_search_update_label(count):
        return ngettext(
            "%(count)d new search result",
            "%(count)d new search results",
            count,
        ) % {"count": count}

    @staticmethod
    def saved_search_body_label(count):
        return ngettext(
            "%(count)d new search result for",
            "%(count)d new search results for",
            count,
        ) % {"count": count}

    @staticmethod
    def saved_search_preheader_label(saved_search, count):
        return ngettext(
            "%(count)d search result for “%(search)s”",
            "%(count)d search results for “%(search)s”",
            count,
        ) % {"count": count, "search": saved_search.q}

    @staticmethod
    def citation_update_label(count):
        return ngettext(
            "%(count)d new citation",
            "%(count)d new citations",
            count,
        ) % {"count": count}

    @staticmethod
    def citation_body_label(count):
        return ngettext(
            "%(count)d new citation of",
            "%(count)d new citations of",
            count,
        ) % {"count": count}

    @staticmethod
    def citation_preheader_label(count):
        return ngettext("%(count)d citation", "%(count)d citations", count) % {
            "count": count
        }

    @staticmethod
    def relationship_update_label(event_type, count):
        relationship_labels = {
            TimelineEvent.EventTypes.NEW_AMENDMENT: (
                "%(count)d new amendment",
                "%(count)d new amendments",
            ),
            TimelineEvent.EventTypes.NEW_REPEAL: (
                "%(count)d new repeal",
                "%(count)d new repeals",
            ),
            TimelineEvent.EventTypes.NEW_COMMENCEMENT: (
                "%(count)d new commencement notice",
                "%(count)d new commencement notices",
            ),
            TimelineEvent.EventTypes.NEW_OVERTURN: (
                "%(count)d new overturning decision",
                "%(count)d new overturning decisions",
            ),
        }
        singular, plural = relationship_labels[event_type]
        return ngettext(singular, plural, count) % {"count": count}

    @staticmethod
    def relationship_body_label(event_type, count):
        relationship_labels = {
            TimelineEvent.EventTypes.NEW_AMENDMENT: (
                "%(count)d new amendment published for",
                "%(count)d new amendments published for",
            ),
            TimelineEvent.EventTypes.NEW_REPEAL: (
                "%(count)d new repeal published for",
                "%(count)d new repeals published for",
            ),
            TimelineEvent.EventTypes.NEW_COMMENCEMENT: (
                "%(count)d new commencement published for",
                "%(count)d new commencements published for",
            ),
            TimelineEvent.EventTypes.NEW_OVERTURN: (
                "%(count)d new overturn published for",
                "%(count)d new overturns published for",
            ),
        }
        singular, plural = relationship_labels[event_type]
        return ngettext(singular, plural, count) % {"count": count}

    @staticmethod
    def relationship_preheader_label(event_type, count):
        relationship_labels = {
            TimelineEvent.EventTypes.NEW_AMENDMENT: (
                "%(count)d amendment",
                "%(count)d amendments",
            ),
            TimelineEvent.EventTypes.NEW_REPEAL: (
                "%(count)d repeal",
                "%(count)d repeals",
            ),
            TimelineEvent.EventTypes.NEW_COMMENCEMENT: (
                "%(count)d commencement",
                "%(count)d commencements",
            ),
            TimelineEvent.EventTypes.NEW_OVERTURN: (
                "%(count)d overturning decision",
                "%(count)d overturning decisions",
            ),
        }
        singular, plural = relationship_labels[event_type]
        return ngettext(singular, plural, count) % {"count": count}

    @staticmethod
    def summary_priority(event_type):
        priorities = {
            # Lead with newly published material from a court or topic the
            # reader follows, then with their saved-search results.
            TimelineEvent.EventTypes.NEW_DOCUMENTS: 1,
            TimelineEvent.EventTypes.SAVED_SEARCH: 2,
            TimelineEvent.EventTypes.NEW_CITATION: 3,
            TimelineEvent.EventTypes.NEW_OVERTURN: 4,
            TimelineEvent.EventTypes.NEW_REPEAL: 5,
            TimelineEvent.EventTypes.NEW_AMENDMENT: 6,
            TimelineEvent.EventTypes.NEW_COMMENCEMENT: 6,
        }
        return priorities[event_type]

    @staticmethod
    def join_update_labels(labels):
        if len(labels) == 1:
            return labels[0]
        if len(labels) == 2:
            return _("%(first)s and %(second)s") % {
                "first": labels[0],
                "second": labels[1],
            }
        return _("%(items)s, and %(last)s") % {
            "items": ", ".join(labels[:-1]),
            "last": labels[-1],
        }

    @classmethod
    def shorten_subject_entity(cls, entity):
        """Keep a featured subject entity readable in a compact inbox subject line."""
        if len(entity) <= cls.SUBJECT_ENTITY_MAX_LENGTH:
            return entity

        shortened = entity[: cls.SUBJECT_ENTITY_MAX_LENGTH - 1].rsplit(" ", 1)[0]
        return f"{shortened or entity[: cls.SUBJECT_ENTITY_MAX_LENGTH - 1]}…"

    @classmethod
    def followed_documents_subject(cls, followed_object, documents, count):
        return _("%(followed_object)s: %(count)d new %(document_kind)s") % {
            "followed_object": cls.shorten_subject_entity(followed_object),
            "count": count,
            "document_kind": cls.document_kind(documents, count),
        }

    @classmethod
    def saved_search_subject(cls, saved_search, count):
        return ngettext(
            "%(search)s: %(count)d new match",
            "%(search)s: %(count)d new matches",
            count,
        ) % {"search": cls.shorten_subject_entity(saved_search.q), "count": count}

    @classmethod
    def citation_subject(cls, document, count):
        return ngettext(
            "New citation of %(document)s",
            "New citations of %(document)s",
            count,
        ) % {"document": cls.shorten_subject_entity(document.title)}

    @classmethod
    def relationship_subject(cls, event_type, document, count):
        subject_labels = {
            TimelineEvent.EventTypes.NEW_AMENDMENT: (
                "New amendment to %(document)s",
                "New amendments to %(document)s",
            ),
            TimelineEvent.EventTypes.NEW_REPEAL: (
                "New repeal affecting %(document)s",
                "New repeals affecting %(document)s",
            ),
            TimelineEvent.EventTypes.NEW_COMMENCEMENT: (
                "New commencement notice for %(document)s",
                "New commencement notices for %(document)s",
            ),
            TimelineEvent.EventTypes.NEW_OVERTURN: (
                "New decision overturning %(document)s",
                "New decisions overturning %(document)s",
            ),
        }
        singular, plural = subject_labels[event_type]
        return ngettext(singular, plural, count) % {
            "document": cls.shorten_subject_entity(document.title)
        }

    @staticmethod
    def digest_subject(summary_items):
        if not summary_items:
            return ""

        lead = min(summary_items, key=lambda item: item["priority"])
        remaining_count = len(summary_items) - 1
        if not remaining_count:
            return lead["subject"]
        return ngettext(
            "%(lead)s and %(count)d more update",
            "%(lead)s and %(count)d more updates",
            remaining_count,
        ) % {"lead": lead["subject"], "count": remaining_count}

    @staticmethod
    def digest_intro(update_count, last_digest_sent_at):
        if last_digest_sent_at:
            return ngettext(
                "%(count)d update since %(date)s",
                "%(count)d updates since %(date)s",
                update_count,
            ) % {
                "count": update_count,
                "date": date_format(timezone.localtime(last_digest_sent_at), "j F Y"),
            }
        return ngettext(
            "%(count)d update since your last alert",
            "%(count)d updates since your last alert",
            update_count,
        ) % {"count": update_count}

    @classmethod
    def digest_preheader(cls, summary_items):
        preheader = " · ".join(item["preheader"] for item in summary_items)
        if len(preheader) <= cls.PREHEADER_MAX_LENGTH:
            return preheader

        shortened = preheader[: cls.PREHEADER_MAX_LENGTH - 1].rsplit(" ", 1)[0]
        return f"{shortened or preheader[: cls.PREHEADER_MAX_LENGTH - 1]}…"

    @classmethod
    def followed_documents(cls, events):
        follows = OrderedDict()
        count = 0
        for event in events:
            follow = event.user_following
            item = follows.setdefault(follow, {"documents": [], "all_documents": []})
            for document in event.subject_documents:
                item["all_documents"].append(document)
                if count < cls.MAX_ENTRIES_PER_CATEGORY:
                    item["documents"].append(document)
                    count += 1
        total_count = sum(len(item["all_documents"]) for item in follows.values())
        return (
            [
                {
                    "followed_object": follow.followed_object_name,
                    "documents": item["documents"],
                    "total_count": len(item["all_documents"]),
                    "heading": cls.followed_documents_heading(
                        follow.followed_object_name,
                        item["all_documents"],
                        len(item["all_documents"]),
                    ),
                    "summary_label": cls.followed_documents_summary_label(
                        follow.followed_object_name,
                        item["all_documents"],
                        len(item["all_documents"]),
                    ),
                    "preheader_label": cls.followed_documents_preheader_label(
                        follow.followed_object_name,
                        item["all_documents"],
                        len(item["all_documents"]),
                    ),
                    "subject": cls.followed_documents_subject(
                        follow.followed_object_name,
                        item["all_documents"],
                        len(item["all_documents"]),
                    ),
                }
                for follow, item in follows.items()
                if item["documents"]
            ],
            total_count,
        )

    @classmethod
    def saved_searches(cls, events):
        searches = []
        count = 0
        for event in events:
            hits = []
            documents_by_id = {
                document.pk: document for document in event.subject_documents
            }
            all_hits = (event.extra_data or {}).get("hits", [])
            for hit in all_hits:
                if count < cls.MAX_ENTRIES_PER_CATEGORY:
                    hit = hit.copy()
                    hit["metadata_document"] = documents_by_id.get(hit["id"])
                    hits.append(hit)
                    count += 1
            if hits:
                searches.append(
                    {
                        "saved_search": event.user_following.saved_search,
                        "hits": hits,
                        "total_count": len(all_hits),
                        "update_label": cls.saved_search_update_label(len(all_hits)),
                        "body_label": cls.saved_search_body_label(len(all_hits)),
                        "preheader_label": cls.saved_search_preheader_label(
                            event.user_following.saved_search, len(all_hits)
                        ),
                        "subject": cls.saved_search_subject(
                            event.user_following.saved_search, len(all_hits)
                        ),
                    }
                )
        return searches, sum(item["total_count"] for item in searches)

    @classmethod
    def citations(cls, events):
        saved_documents = OrderedDict()
        count = 0
        for event in events:
            saved_document = event.user_following.saved_document
            document = saved_document.document if saved_document else None
            if not document:
                continue

            item = saved_documents.setdefault(
                document, {"citing_documents": [], "total_count": 0}
            )
            for citing_document in event.subject_documents:
                item["total_count"] += 1
                if count >= cls.MAX_ENTRIES_PER_CATEGORY:
                    continue
                provision_citations = ProvisionCitation.objects.filter(
                    citing_document=citing_document,
                    work=saved_document.work,
                    whole_work=False,
                )[:2]
                item["citing_documents"].append(
                    {
                        "document": citing_document,
                        "provision_citations": provision_citations,
                    }
                )
                count += 1

        return (
            [
                {
                    "saved_document": document,
                    "citing_documents": item["citing_documents"],
                    "total_count": item["total_count"],
                    "update_label": cls.citation_update_label(item["total_count"]),
                    "body_label": cls.citation_body_label(item["total_count"]),
                    "preheader_label": cls.citation_preheader_label(
                        item["total_count"]
                    ),
                    "subject": cls.citation_subject(document, item["total_count"]),
                }
                for document, item in saved_documents.items()
                if item["citing_documents"]
            ],
            sum(item["total_count"] for item in saved_documents.values()),
        )

    @classmethod
    def relationships(cls, events):
        saved_documents = OrderedDict()
        count = 0
        for event in events:
            saved_document = event.user_following.saved_document
            document = saved_document.document if saved_document else None
            if not document:
                continue

            relationships = saved_documents.setdefault(document, OrderedDict())
            relationship = relationships.setdefault(
                event.event_type,
                {"documents": [], "total_count": 0, "event_type": event.event_type},
            )
            for related_document in event.subject_documents:
                relationship["total_count"] += 1
                if count < cls.MAX_ENTRIES_PER_CATEGORY:
                    relationship["documents"].append(related_document)
                    count += 1

        for relationships in saved_documents.values():
            for relationship in relationships.values():
                relationship["update_label"] = cls.relationship_update_label(
                    relationship["event_type"], relationship["total_count"]
                )
                relationship["body_label"] = cls.relationship_body_label(
                    relationship["event_type"], relationship["total_count"]
                )
                relationship["preheader_label"] = cls.relationship_preheader_label(
                    relationship["event_type"], relationship["total_count"]
                )

        return (
            [
                {"saved_document": document, "relationships": relationships}
                for document, relationships in saved_documents.items()
                if any(item["documents"] for item in relationships.values())
            ],
            sum(
                item["total_count"]
                for relationships in saved_documents.values()
                for item in relationships.values()
            ),
        )

    @classmethod
    def digest_context(cls, user, events):
        followed_events = [
            event
            for event in events
            if event.event_type == TimelineEvent.EventTypes.NEW_DOCUMENTS
        ]
        search_events = [
            event
            for event in events
            if event.event_type == TimelineEvent.EventTypes.SAVED_SEARCH
        ]
        citation_events = [
            event
            for event in events
            if event.event_type == TimelineEvent.EventTypes.NEW_CITATION
        ]
        relationship_events = [
            event
            for event in events
            if event.event_type
            in [
                relationship.event_type
                for relationship in TimelineEvent.RELATIONSHIP_EVENT_MAP.values()
            ]
        ]

        followed_documents, followed_total = cls.followed_documents(followed_events)
        saved_searches, searches_total = cls.saved_searches(search_events)
        citations, citations_total = cls.citations(citation_events)
        relationships, relationships_total = cls.relationships(relationship_events)

        summary_items = []
        summary_items.extend(
            {
                "label": item["summary_label"],
                "subject": item["subject"],
                "preheader": item["preheader_label"],
                "priority": cls.summary_priority(
                    TimelineEvent.EventTypes.NEW_DOCUMENTS
                ),
                "section_id": "followed-documents",
            }
            for item in followed_documents
        )
        summary_items.extend(
            {
                "label": _("“%(search)s” – %(update_label)s")
                % {
                    "search": item["saved_search"].q,
                    "update_label": item["update_label"],
                },
                "subject": item["subject"],
                "preheader": item["preheader_label"],
                "priority": cls.summary_priority(TimelineEvent.EventTypes.SAVED_SEARCH),
                "section_id": "saved-searches",
            }
            for item in saved_searches
        )
        document_summary_items = OrderedDict()
        for item in citations:
            document = item["saved_document"]
            document_summary_items[document] = {
                "document": document,
                "update_labels": [item["update_label"]],
                "preheader_labels": [item["preheader_label"]],
                "subject": item["subject"],
                "priority": cls.summary_priority(TimelineEvent.EventTypes.NEW_CITATION),
                "has_relationships": False,
            }
        for item in relationships:
            document = item["saved_document"]
            summary_item = document_summary_items.setdefault(
                document,
                {
                    "document": document,
                    "update_labels": [],
                    "preheader_labels": [],
                    "subject": None,
                    "priority": None,
                    "has_relationships": True,
                },
            )
            for relationship in item["relationships"].values():
                if not relationship["documents"]:
                    continue
                summary_item["has_relationships"] = True
                priority = cls.summary_priority(relationship["event_type"])
                summary_item["update_labels"].append(relationship["update_label"])
                summary_item["preheader_labels"].append(relationship["preheader_label"])
                if (
                    summary_item["priority"] is None
                    or priority < summary_item["priority"]
                ):
                    summary_item["priority"] = priority
                    summary_item["subject"] = cls.relationship_subject(
                        relationship["event_type"],
                        document,
                        relationship["total_count"],
                    )
        summary_items.extend(
            {
                "label": _("%(document)s – %(updates)s")
                % {
                    "document": item["document"].title,
                    "updates": cls.join_update_labels(item["update_labels"]),
                },
                "subject": item["subject"],
                "preheader": cls.join_update_labels(item["preheader_labels"]),
                "priority": item["priority"],
                "section_id": (
                    "relationships" if item["has_relationships"] else "citations"
                ),
            }
            for item in document_summary_items.values()
        )

        displayed_events = followed_events + search_events
        if citations:
            displayed_events += citation_events
        if relationships:
            displayed_events += relationship_events

        total_update_count = (
            followed_total + searches_total + citations_total + relationships_total
        )
        section_count = sum(
            bool(items)
            for items in [followed_documents, saved_searches, citations, relationships]
        )
        last_digest_sent_at = cls.last_digest_sent_at(user)
        return {
            "user": user,
            "summary_items": summary_items[: cls.MAX_SUMMARY_ENTRIES],
            "summary_more_count": max(len(summary_items) - cls.MAX_SUMMARY_ENTRIES, 0),
            "summary_has_anchor_links": section_count > 3,
            "digest_subject": cls.digest_subject(summary_items),
            "preheader": cls.digest_preheader(summary_items),
            "digest_intro": cls.digest_intro(total_update_count, last_digest_sent_at),
            "email_alert_frequency": user.userprofile.get_email_alert_frequency_display().lower(),
            "followed_documents": followed_documents,
            "followed_total": followed_total,
            "followed_more": followed_total > cls.MAX_ENTRIES_PER_CATEGORY,
            "saved_searches": saved_searches,
            "searches_total": searches_total,
            "searches_more": searches_total > cls.MAX_ENTRIES_PER_CATEGORY,
            "citations": citations,
            "citations_total": citations_total,
            "citations_more": citations_total > cls.MAX_ENTRIES_PER_CATEGORY,
            "relationships": relationships,
            "relationships_total": relationships_total,
            "relationships_more": relationships_total > cls.MAX_ENTRIES_PER_CATEGORY,
            "timeline_url_path": reverse("my_home") + "#timeline",
            "manage_url_path": reverse("edit_account"),
            "utm_campaign": "email_digest",
            "displayed_events": displayed_events,
        }

    @classmethod
    def send_digest_email(cls, user):
        if not cls.is_digest_due(user):
            return False
        if cls.already_sent_digest_within_last_24_hours(user):
            log.info(
                "A timeline email digest was sent within the last 24 hours for %s", user
            )
            return False

        events = cls.get_user_events(user)
        if not events:
            return False

        if not settings.PEACHJAM["EMAIL_ALERTS_ENABLED"] or not user.email:
            return False

        with override(user.userprofile.preferred_language.pk):
            context = cls.digest_context(user, events)
            if not context["displayed_events"] or not context["summary_items"]:
                log.info("No renderable timeline events to alert for %s", user)
                return False
            send_templated_mail(
                template_name="email_alert_digest",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                context=context,
            )

        TimelineEvent.objects.filter(
            pk__in=[event.pk for event in context["displayed_events"]]
        ).update(email_alert_sent_at=timezone.now())
        return True
