from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.vary import vary_on_cookie

from peachjam_search.omnibox import OmniboxShortcuts


@method_decorator([never_cache, vary_on_cookie], name="dispatch")
class OmniboxShortcutsView(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse(OmniboxShortcuts().for_user(request.user))
