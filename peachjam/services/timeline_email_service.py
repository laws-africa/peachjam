from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import override
from templated_email import send_templated_mail

from peachjam.models import TimelineEvent


class TimelineEmailService:
    @staticmethod
    def send_for_all_events():
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
            TimelineEmailService.send_new_documents(user_id)

        for user_id in saved_search_user_ids:
            TimelineEmailService.send_saved_search(user_id)

    @staticmethod
    def send_saved_search(user):
        events = TimelineEvent.objects.filter(
            email_alert_sent_at__isnull=True,
            event_type=TimelineEvent.EventTypes.SAVED_SEARCH,
            user_following__user=user,
        ).select_related("user_following")

        if not events.exists():
            return

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

    @staticmethod
    def send_new_documents(user):
        events = (
            TimelineEvent.objects.filter(
                email_alert_sent_at__isnull=True,
                event_type=TimelineEvent.EventTypes.NEW_DOCUMENTS,
                user_following__user=user,
            )
            .select_related("user_following")
            .prefetch_related("subject_documents")
        )

        if not events.exists():
            return

        follows_map = {}
        for ev in events:
            key = ev.user_following.followed_object
            follows_map.setdefault(key, set()).update(ev.subject_documents.all())

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

        events.update(email_alert_sent_at=timezone.now())
