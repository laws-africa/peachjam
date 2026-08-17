import logging
from collections import OrderedDict
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import override
from templated_email import send_templated_mail

from peachjam.models import ProvisionCitation, TimelineEvent
from peachjam.tasks import send_timeline_digest_email_alert

log = logging.getLogger(__name__)


class TimelineEmailService:
    MAX_ENTRIES_PER_CATEGORY = 10

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

    @classmethod
    def followed_documents(cls, events):
        follows = OrderedDict()
        count = 0
        has_more = False
        for event in events:
            follow = event.user_following
            documents = follows.setdefault(follow, [])
            for document in event.subject_documents:
                if count < cls.MAX_ENTRIES_PER_CATEGORY:
                    documents.append(document)
                    count += 1
                else:
                    has_more = True
        return (
            [
                {"followed_object": follow.followed_object_name, "documents": documents}
                for follow, documents in follows.items()
                if documents
            ],
            has_more,
        )

    @classmethod
    def saved_searches(cls, events):
        searches = []
        count = 0
        has_more = False
        for event in events:
            hits = []
            for hit in (event.extra_data or {}).get("hits", []):
                if count < cls.MAX_ENTRIES_PER_CATEGORY:
                    hits.append(hit)
                    count += 1
                else:
                    has_more = True
            if hits:
                searches.append(
                    {"saved_search": event.user_following.saved_search, "hits": hits}
                )
        return searches, has_more

    @classmethod
    def citations(cls, events):
        saved_documents = OrderedDict()
        count = 0
        has_more = False
        for event in events:
            saved_document = event.user_following.saved_document
            document = saved_document.document if saved_document else None
            if not document:
                continue

            citing_documents = saved_documents.setdefault(document, [])
            for citing_document in event.subject_documents:
                if count >= cls.MAX_ENTRIES_PER_CATEGORY:
                    has_more = True
                    continue
                provision_citations = ProvisionCitation.objects.filter(
                    citing_document=citing_document,
                    work=saved_document.work,
                    whole_work=False,
                )[:2]
                citing_documents.append(
                    {
                        "document": citing_document,
                        "provision_citations": provision_citations,
                    }
                )
                count += 1

        return (
            [
                {"saved_document": document, "citing_documents": citing_documents}
                for document, citing_documents in saved_documents.items()
                if citing_documents
            ],
            has_more,
        )

    @classmethod
    def relationships(cls, events):
        saved_documents = OrderedDict()
        count = 0
        has_more = False
        for event in events:
            saved_document = event.user_following.saved_document
            document = saved_document.document if saved_document else None
            if not document:
                continue

            relationships = saved_documents.setdefault(document, OrderedDict())
            relationship = relationships.setdefault(
                event.event_type,
                {"label": str(event.description_text()), "documents": []},
            )
            for related_document in event.subject_documents:
                if count < cls.MAX_ENTRIES_PER_CATEGORY:
                    relationship["documents"].append(related_document)
                    count += 1
                else:
                    has_more = True

        return (
            [
                {"saved_document": document, "relationships": relationships}
                for document, relationships in saved_documents.items()
                if any(item["documents"] for item in relationships.values())
            ],
            has_more,
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

        followed_documents, followed_more = cls.followed_documents(followed_events)
        saved_searches, searches_more = cls.saved_searches(search_events)
        citations, citations_more = cls.citations(citation_events)
        relationships, relationships_more = cls.relationships(relationship_events)

        displayed_events = followed_events + search_events
        if citations:
            displayed_events += citation_events
        if relationships:
            displayed_events += relationship_events

        return {
            "user": user,
            "followed_documents": followed_documents,
            "followed_more": followed_more,
            "saved_searches": saved_searches,
            "searches_more": searches_more,
            "citations": citations,
            "citations_more": citations_more,
            "relationships": relationships,
            "relationships_more": relationships_more,
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
