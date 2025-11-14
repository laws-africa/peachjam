from django.utils import timezone

from .follow_query_service import FollowQueryService
from .timeline_event_service import TimelineEventService


class FollowUpdateService:
    @staticmethod
    def update_follow(follow):
        if follow.is_new_docs:
            return FollowUpdateService._update_new_docs(follow)

        if follow.is_saved_search:
            return FollowUpdateService._update_search(follow)

    @staticmethod
    def _update_new_docs(follow):
        qs = FollowQueryService.documents_for_follow(follow)
        qs = qs.preferred_language(follow.user.userprofile.preferred_language.iso_639_3)

        if follow.last_alerted_at:
            qs = qs.filter(created_at__gt=follow.last_alerted_at)

        docs = list(qs[:10])
        if not docs:
            return False

        TimelineEventService.add_documents_event(follow, docs)
        follow.last_alerted_at = timezone.now()
        follow.save(update_fields=["last_alerted_at"])
        return True

    @staticmethod
    def _update_search(follow):
        hits = follow.saved_search.find_new_hits()
        cutoff = follow.last_alerted_at

        if cutoff:
            hits = [h for h in hits if h.document.created_at > cutoff][:10]

        if not hits:
            return False

        TimelineEventService.add_search_hits_event(follow, hits)
        follow.last_alerted_at = timezone.now()
        follow.save(update_fields=["last_alerted_at"])
        return True
