import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.sites.models import Site
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import override
from templated_email import send_templated_mail

from peachjam.models import ProvisionCitation, TimelineEvent
from peachjam.tasks import (
    send_new_citation_email_alert,
    send_new_document_email_alert,
    send_new_relationship_email_alert,
    send_saved_search_email_alert,
)

log = logging.getLogger(__name__)


class TimelineEmailService:
    @staticmethod
    def already_alerted_today(user, event_type):
        q = Q()
        last_24_hrs = timezone.now() - timedelta(hours=24)

        if type(event_type) == list:
            q = Q(event_type__in=event_type)
        elif type(event_type) == TimelineEvent.EventTypes:
            q = Q(event_type=event_type)

        q &= Q(
            email_alert_sent_at__gte=last_24_hrs,
            user_following__user=user,
        )

        email_sent = TimelineEvent.objects.filter(q).exists()
        if email_sent:
            log.info(
                "%s email for %s has been sent within the last 24hrs: %s",
                event_type,
                user,
                last_24_hrs,
            )
            return True
        return False

    @staticmethod
    def send_email_alerts():
        events = TimelineEvent.objects.filter(email_alert_sent_at__isnull=True)
        if not events.exists():
            return

        new_doc_user_ids = (
            events.filter(event_type=TimelineEvent.EventTypes.NEW_DOCUMENTS)
            .values_list("user_following__user_id", flat=True)
            .distinct()
        )
        saved_search_user_ids = (
            events.filter(event_type=TimelineEvent.EventTypes.SAVED_SEARCH)
            .values_list("user_following__user_id", flat=True)
            .distinct()
        )

        new_citation_user_ids = (
            events.filter(event_type=TimelineEvent.EventTypes.NEW_CITATION)
            .values_list("user_following__user_id", flat=True)
            .distinct()
        )

        relationship_events_types = [
            ev.event_type for ev in TimelineEvent.PREDICATE_MAP.values()
        ]
        new_relationship_user_ids = (
            events.filter(event_type__in=relationship_events_types)
            .values_list("user_following__user_id", flat=True)
            .distinct()
        )

        for user_id in new_doc_user_ids:
            send_new_document_email_alert(user_id)

        for user_id in saved_search_user_ids:
            send_saved_search_email_alert(user_id)

        for user_id in new_citation_user_ids:
            send_new_citation_email_alert(user_id)

        for user_id in new_relationship_user_ids:
            send_new_relationship_email_alert(user_id)

    @staticmethod
    def send_new_documents_email(user):

        if TimelineEmailService.already_alerted_today(
            user, TimelineEvent.EventTypes.NEW_DOCUMENTS
        ):
            return

        events = TimelineEvent.objects.prefetch_subject_documents(user).filter(
            email_alert_sent_at__isnull=True,
            event_type=TimelineEvent.EventTypes.NEW_DOCUMENTS,
            user_following__user=user,
        )

        if not events.exists():
            log.info("No new documents events to alert for %s", user)
            return

        if settings.PEACHJAM["EMAIL_ALERTS_ENABLED"]:
            events = [
                TimelineEvent.objects.attach_subject_documents(ev) for ev in events
            ]

            follows_map = {}
            for ev in events:
                key = ev.user_following.followed_object
                follows_map.setdefault(key, set()).update(ev.subject_documents)

            follows = [
                {"followed_object": key, "documents": list(docs)[:10]}
                for key, docs in follows_map.items()
            ]

            context = {
                "followed_documents": follows,
                "user": user,
                "manage_url_path": reverse("user_following_list"),
            }

            with override(user.userprofile.preferred_language.pk):
                send_templated_mail(
                    template_name="user_following_alert",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    context=context,
                )

        for ev in events:
            ev.mark_as_sent()

    @staticmethod
    def send_saved_search_email(user):

        events = TimelineEvent.objects.prefetch_subject_documents(user).filter(
            email_alert_sent_at__isnull=True,
            event_type=TimelineEvent.EventTypes.SAVED_SEARCH,
            user_following__user=user,
        )

        if not events.exists():
            log.info("No saved search events to alert for %s", user)
            return

        if settings.PEACHJAM["EMAIL_ALERTS_ENABLED"]:
            events = [
                TimelineEvent.objects.attach_subject_documents(ev) for ev in events
            ]

            for ev in events:
                context = {
                    "user": user,
                    "hits": (ev.extra_data or {}).get("hits", []),
                    "saved_search": ev.user_following.saved_search,
                    "manage_url_path": reverse("search:saved_search_list"),
                }

                with override(user.userprofile.preferred_language.pk):
                    send_templated_mail(
                        template_name="search_alert",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        context=context,
                    )

        for ev in events:
            ev.mark_as_sent()

    @staticmethod
    def send_new_citation_email(user):

        if TimelineEmailService.already_alerted_today(
            user, TimelineEvent.EventTypes.NEW_CITATION
        ):
            return

        events = TimelineEvent.objects.prefetch_subject_documents(user).filter(
            email_alert_sent_at__isnull=True,
            event_type=TimelineEvent.EventTypes.NEW_CITATION,
            user_following__user=user,
        )

        if not events.exists():
            log.info("No new citation events to alert for %s", user)
            return

        if settings.PEACHJAM["EMAIL_ALERTS_ENABLED"]:
            events = [
                TimelineEvent.objects.attach_subject_documents(ev) for ev in events
            ]

            context = {
                "user": user,
                "saved_documents": [],
                "manage_url_path": reverse("folder_list"),
            }

            for ev in events:
                citing_documents = []
                for doc in ev.subject_documents[:5]:
                    provision_citations = ProvisionCitation.objects.filter(
                        citing_document=doc,
                        work=ev.user_following.saved_document.document.work,
                        whole_work=False,
                    )[:2]
                    citing_documents.append(
                        {
                            "document": doc,
                            "provision_citations": provision_citations,
                        }
                    )

                context["saved_documents"].append(
                    {
                        "saved_document": ev.user_following.saved_document.document,
                        "citing_documents": citing_documents,
                    }
                )
            site = Site.objects.get_current()
            context["site_domain"] = f"https://{site.domain}"

            # render html template string
            context["html_body"] = render_to_string(
                "peachjam/emails/new_citation_alert_body.html", context=context
            )
            subject_line = f"New citations for {context['saved_documents'][0]['saved_document'].title}"
            saved_docs_length = len(context["saved_documents"])
            if saved_docs_length > 1:
                subject_line += f" and {saved_docs_length} more"

            context["subject_line"] = subject_line

            with override(user.userprofile.preferred_language.pk):
                send_templated_mail(
                    template_name="new_citation_alert",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    context=context,
                )

        for ev in events:
            ev.mark_as_sent()

    @staticmethod
    def send_new_relationship_email(user):
        relationship_events_types = [
            ev.event_type for ev in TimelineEvent.PREDICATE_MAP.values()
        ]

        if TimelineEmailService.already_alerted_today(user, relationship_events_types):
            return

        events = TimelineEvent.objects.prefetch_subject_documents(user).filter(
            email_alert_sent_at__isnull=True,
            event_type__in=relationship_events_types,
            user_following__user=user,
        )

        if not events.exists():
            log.info("No new relationship events to alert for %s", user)
            return

        if settings.PEACHJAM["EMAIL_ALERTS_ENABLED"]:
            events = [
                TimelineEvent.objects.attach_subject_documents(ev) for ev in events
            ]
            saved_documents_map = {}
            for ev in events:
                key = ev.user_following.followed_object
                saved_documents_map.setdefault(key, {}).setdefault(
                    ev.description_text(), []
                ).extend(ev.subject_documents)

            saved_documents = [
                {"saved_document": key, "relationships": value}
                for key, value in saved_documents_map.items()
            ]
            site = Site.objects.get_current()

            context = {
                "saved_documents": saved_documents,
                "user": user,
                "manage_url_path": reverse("folder_list"),
                "site_domain": f"https://{site.domain}",
            }

            context["html_body"] = render_to_string(
                "peachjam/emails/new_relationship_alert_body.html", context=context
            )

            with override(user.userprofile.preferred_language.pk):
                send_templated_mail(
                    template_name="new_relationship_alert",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    context=context,
                )

        for ev in events:
            ev.mark_as_sent()
