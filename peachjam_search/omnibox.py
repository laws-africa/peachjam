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
            for saved in (
                user.saved_documents.filter(subscription_locked_at__isnull=True)
                .select_related("work")
                .order_by("-updated_at", "-pk")
            ):
                data["saved_items"].append(
                    {
                        "id": f"document-{saved.pk}",
                        "type": "document",
                        "work_id": saved.work_id,
                        "text": saved.work.title,
                        "url": saved.get_absolute_url(),
                    }
                )
            if user.has_perm("peachjam.view_folder"):
                for folder in user.folders.filter(
                    subscription_locked_at__isnull=True
                ).order_by("-created_at", "-pk"):
                    data["saved_items"].append(
                        {
                            "id": f"folder-{folder.pk}",
                            "type": "folder",
                            "text": folder.name,
                            "url": folder.get_absolute_url(),
                        }
                    )
        if pjs.save_searches_enabled and user.has_perm(
            "peachjam_search.view_savedsearch"
        ):
            for search in user.saved_searches.filter(
                subscription_locked_at__isnull=True
            ).order_by("-created_at", "-pk"):
                data["saved_items"].append(
                    {
                        "id": f"search-{search.pk}",
                        "type": "saved_search",
                        "text": str(search),
                        "url": search.get_absolute_url(),
                    }
                )
        return data

    def recent_searches(self, user):
        """Return distinct recent simple searches with their filters and search mode."""
        traces = (
            SearchTrace.objects.filter(
                user=user,
                kind=SearchTrace.Kind.DOCUMENTS,
                status=SearchTrace.Status.COMPLETED,
                page=1,
            )
            .only(
                "id", "search", "field_searches", "filters", "ordering", "mode", "page"
            )
            .exclude(search="")
            .order_by("-created_at")[:100]
        )
        items = []
        seen = set()
        for trace in traces:
            if not trace.search.strip() or trace.field_searches:
                continue
            url = trace.get_search_url()
            if url in seen:
                continue
            seen.add(url)
            items.append(
                {
                    "id": str(trace.pk),
                    "type": "history",
                    "text": trace.search,
                    "url": url,
                }
            )
            if len(items) == 12:
                break
        return items
