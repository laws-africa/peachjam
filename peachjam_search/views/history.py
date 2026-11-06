from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest, JsonResponse
from django.views import View

from peachjam_search.omnibox import OmniboxShortcuts


class SearchHistoryView(LoginRequiredMixin, View):
    """Update the signed-in user's recent searches, including cached searches."""

    def post(self, request):
        url = request.POST.get("url", "")
        text = request.POST.get("text", "").strip()
        action = request.POST.get("action")
        try:
            parsed = urlsplit(url)
            params = parse_qs(parsed.query)
        except ValueError:
            return HttpResponseBadRequest("Invalid search URL")
        if (
            action not in {"record", "remove"}
            or not text
            or len(text) > 4098
            or len(url) > 16384
            or parsed.netloc
            or parsed.scheme
            or not (params.get("q") or params.get("a"))
        ):
            return HttpResponseBadRequest("Invalid search history entry")
        return JsonResponse(
            OmniboxShortcuts().update_history(
                request.user, url, text, action == "remove"
            )
        )
