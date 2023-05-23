from django.http import Http404
from django.views.generic import TemplateView

from peachjam.models.settings import pj_settings


class MetabaseStatsView(TemplateView):
    template_name = "peachjam/metabase_stats.html"

    def get(self, request, *args, **kwargs):
        if not pj_settings().metabase_dashboard_link:
            raise Http404
        return super().get(request, *args, **kwargs)
