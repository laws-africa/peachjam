from django.conf import settings
from django.urls import reverse
from django.utils.translation import override
from templated_email import send_templated_mail

from peachjam.models import TimelineEvent
from peachjam.tasks import send_new_document_email_alert, send_saved_search_email_alert


class TimelineEmailService:
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

        for user_id in new_doc_user_ids:
            send_new_document_email_alert(user_id)

        for user_id in saved_search_user_ids:
            send_saved_search_email_alert(user_id)

    @staticmethod
    def send_new_documents_email(user):
        events = (
            TimelineEvent.objects.prefetch_subject_documents(user)
            .filter(
                email_alert_sent_at__isnull=True,
                event_type=TimelineEvent.EventTypes.NEW_DOCUMENTS,
                user_following__user=user,
            )
            .select_related("user_following")
        )

        if not events.exists():
            return

        events = [TimelineEvent.objects.attach_subject_documents(ev) for ev in events]

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
        events = (
            TimelineEvent.objects.prefetch_subject_documents(user)
            .filter(
                email_alert_sent_at__isnull=True,
                event_type=TimelineEvent.EventTypes.SAVED_SEARCH,
                user_following__user=user,
            )
            .select_related("user_following")
        )

        if not events.exists():
            return

        events = [TimelineEvent.objects.attach_subject_documents(ev) for ev in events]

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
                ev.mark_as_sent()
