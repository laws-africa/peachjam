import logging
from collections import OrderedDict
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import ngettext, override
from templated_email import send_templated_mail

from peachjam.models import ProvisionCitation, TimelineEvent
from peachjam.tasks import send_timeline_digest_email_alert

log = logging.getLogger(__name__)


class TimelineEmailService:
    MAX_ENTRIES_PER_CATEGORY = 10
    SUBJECT_ENTITY_MAX_LENGTH = 500

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

    @staticmethod
    def saved_search_heading(saved_search, count):
        return ngettext(
            "%(count)d new match for “%(search)s”",
            "%(count)d new matches for “%(search)s”",
            count,
        ) % {"count": count, "search": saved_search.q}

    @staticmethod
    def citation_heading(document, count):
        return ngettext(
            "%(count)d new citation of %(document)s",
            "%(count)d new citations of %(document)s",
            count,
        ) % {"count": count, "document": document.title}

    @staticmethod
    def relationship_heading(event_type, count):
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
            return _("Your latest legal updates")

        subject = summary_items[0]["subject"]
        if len(summary_items) > 1:
            subject = _("%(subject)s and other updates") % {"subject": subject}
        return subject

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
            all_hits = (event.extra_data or {}).get("hits", [])
            for hit in all_hits:
                if count < cls.MAX_ENTRIES_PER_CATEGORY:
                    hits.append(hit)
                    count += 1
            if hits:
                searches.append(
                    {
                        "saved_search": event.user_following.saved_search,
                        "hits": hits,
                        "total_count": len(all_hits),
                        "heading": cls.saved_search_heading(
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
                    "heading": cls.citation_heading(document, item["total_count"]),
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
                relationship["label"] = cls.relationship_heading(
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
                "anchor": "followed-documents",
                "label": item["heading"],
                "subject": item["subject"],
            }
            for item in followed_documents
        )
        summary_items.extend(
            {
                "anchor": "saved-searches",
                "label": item["heading"],
                "subject": item["subject"],
            }
            for item in saved_searches
        )
        summary_items.extend(
            {
                "anchor": "citations",
                "label": item["heading"],
                "subject": item["subject"],
            }
            for item in citations
        )
        summary_items.extend(
            {
                "anchor": "relationships",
                "label": f"{relationship['label']} {document.title}",
                "subject": cls.relationship_subject(
                    relationship["event_type"],
                    document,
                    relationship["total_count"],
                ),
            }
            for item in relationships
            for document in [item["saved_document"]]
            for relationship in item["relationships"].values()
            if relationship["documents"]
        )

        displayed_events = followed_events + search_events
        if citations:
            displayed_events += citation_events
        if relationships:
            displayed_events += relationship_events

        return {
            "user": user,
            "summary_items": summary_items,
            "digest_subject": cls.digest_subject(summary_items),
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
            "manage_following_url_path": reverse("user_following_list"),
            "manage_searches_url_path": reverse("search:saved_search_list"),
            "manage_saved_documents_url_path": reverse("folder_list"),
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

        context = cls.digest_context(user, events)
        if not context["displayed_events"]:
            log.info("No renderable timeline events to alert for %s", user)
            return False

        if not settings.PEACHJAM["EMAIL_ALERTS_ENABLED"] or not user.email:
            return False

        with override(user.userprofile.preferred_language.pk):
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
