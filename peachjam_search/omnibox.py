import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit

from django.urls import reverse

from peachjam.models import pj_settings
from peachjam_search.models import SearchHistory, SearchTrace


class OmniboxShortcuts:
    """Collect navigation shortcuts belonging to the current user."""

    def for_user(self, user):
        """Return private shortcut data without adding it to cacheable page HTML."""
        data = {"user_id": None, "recent_searches": [], "saved_items": []}
        if not user.is_authenticated:
            return data

        data["user_id"] = user.pk
        data.update(self.history(user))
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

    def recent_searches(self, user, limit=12):
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
            key = self.search_key(url)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "id": str(trace.pk),
                    "type": "history",
                    "text": trace.search,
                    "url": url,
                }
            )
            if len(items) == limit:
                break
        return items

    def search_key(self, url):
        """Identify equivalent searches without analytics parameters or explicit defaults."""
        defaults = {"page": "1", "ordering": "-score", "mode": "text"}
        params = []
        for key, value in parse_qsl(urlsplit(url).query):
            if key in {"suggestion", "gsc.tab"} or defaults.get(key) == value:
                continue
            if key == "q":
                value = " ".join(value.split()).lower()
            params.append((key, value))
        return hashlib.sha256(urlencode(sorted(set(params))).encode()).hexdigest()

    def history(self, user):
        """Merge account history with legacy traces, respecting account-wide removals."""
        history = SearchHistory.objects.filter(user=user)
        entries = list(history.filter(removed=False)[:12])
        items = [
            {
                "id": f"history-{entry.pk}",
                "type": "history",
                "text": entry.text,
                "url": reverse("search:search") + "?" + entry.query_string,
            }
            for entry in entries
        ]
        if len(items) == 12:
            return {"recent_searches": items}

        candidates = {
            self.search_key(item["url"]): item
            for item in self.recent_searches(user, limit=100)
        }
        # Only check keys from the bounded trace window, including removals and
        # account entries outside the most recent twelve.
        seen = set(
            history.filter(key__in=candidates).order_by().values_list("key", flat=True)
        )
        for key, item in candidates.items():
            if key not in seen:
                items.append(item)
            if len(items) >= 12:
                break
        return {"recent_searches": items}

    def update_history(self, user, url, text, removed):
        """Record a completed search or remove it from account history without deleting analytics."""
        query_string = urlsplit(url).query
        SearchHistory.objects.update_or_create(
            user=user,
            key=self.search_key(url),
            defaults={"query_string": query_string, "text": text, "removed": removed},
        )
        return self.history(user)
