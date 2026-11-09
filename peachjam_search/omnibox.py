from django.db.models import F, Window
from django.db.models.functions import RowNumber
from django.urls import reverse

from peachjam.models import pj_settings
from peachjam_search.models import SearchTrace


class OmniboxShortcuts:
    """Collect navigation shortcuts belonging to the current user."""

    def for_user(self, user):
        """Return private shortcut data without adding it to cacheable page HTML."""
        data = {"user_id": None, "recent_searches": [], "saved_items": []}
        if not user.is_authenticated:
            return data

        data["user_id"] = user.pk
        data["recent_searches"] = self.recent_searches(user)
        pjs = pj_settings()
        if pjs.save_documents_enabled:
            data["saved_items"].extend(self.saved_documents(user))
            if user.has_perm("peachjam.view_folder"):
                data["saved_items"].extend(self.saved_folders(user))
        if pjs.save_searches_enabled and user.has_perm(
            "peachjam_search.view_savedsearch"
        ):
            data["saved_items"].extend(self.saved_searches(user))
        return data

    def saved_documents(self, user):
        """Load the user's available saved documents in newest-saved order."""
        return [
            {
                "id": f"document-{saved.pk}",
                "type": "document",
                "work_id": saved.work_id,
                "text": saved.work.title,
                "url": saved.get_absolute_url(),
            }
            for saved in user.saved_documents.filter(
                subscription_locked_at__isnull=True
            )
            .select_related("work")
            .order_by("-updated_at", "-pk")
        ]

    def saved_folders(self, user):
        """Load the user's available saved folders in newest-saved order."""
        return [
            {
                "id": f"folder-{folder.pk}",
                "type": "folder",
                "text": folder.name,
                "url": folder.get_absolute_url(),
            }
            for folder in user.folders.filter(
                subscription_locked_at__isnull=True
            ).order_by("-created_at", "-pk")
        ]

    def saved_searches(self, user):
        """Load the user's available saved searches in newest-saved order."""
        return [
            {
                "id": f"search-{search.pk}",
                "type": "saved_search",
                "text": str(search),
                "url": search.get_absolute_url(),
            }
            for search in user.saved_searches.filter(
                subscription_locked_at__isnull=True
            ).order_by("-created_at", "-pk")
        ]

    def recent_searches(self, user, limit=12):
        """Return the latest trace for each visible simple search."""
        traces = SearchTrace.objects.filter(user=user).for_search_history()
        latest = (
            traces.annotate(
                history_rank=Window(
                    expression=RowNumber(),
                    partition_by=[F("history_text")],
                    order_by=[F("created_at").desc(), F("pk").desc()],
                )
            )
            .filter(history_rank=1)
            .values("pk")
        )
        return [
            {
                "id": str(trace.pk),
                "type": "history",
                "text": trace.search,
                "url": trace.get_search_url(),
                "delete_url": reverse("search:history_delete", args=[trace.pk]),
            }
            for trace in SearchTrace.objects.filter(pk__in=latest)
            .only("id", "search", "filters", "mode", "ordering", "page")
            .order_by("-created_at", "-pk")[:limit]
        ]
