from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from peachjam_search.models import SearchTrace
from peachjam_search.omnibox import OmniboxShortcuts


@method_decorator(never_cache, name="dispatch")
class SearchHistoryView(LoginRequiredMixin, View):
    """Load the signed-in user's history after a completed search."""

    def get(self, request):
        return JsonResponse(
            {"recent_searches": OmniboxShortcuts().recent_searches(request.user)}
        )


@method_decorator(never_cache, name="dispatch")
class SearchHistoryDeleteView(LoginRequiredMixin, View):
    """Hide a search and its repetitions while preserving analytics."""

    def post(self, request, pk):
        traces = SearchTrace.objects.filter(user=request.user).for_search_history()
        trace = get_object_or_404(traces, pk=pk)
        traces.filter(history_text=trace.history_text).update(hidden=True)
        return JsonResponse(
            {"recent_searches": OmniboxShortcuts().recent_searches(request.user)}
        )
