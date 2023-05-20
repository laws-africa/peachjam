from django.http import Http404
from django.views.generic import TemplateView

from peachjam.models.settings import pj_settings


class MetabaseStatsView(TemplateView):
    template_name = "peachjam/metabase_stats.html"

    def get(self, request, *args, **kwargs):
        if pj_settings().metabase_dashboard_link:
            context = self.get_context_data(**kwargs)
            context["metabase_embed"] = pj_settings().metabase_dashboard_link
            return self.render_to_response(context)
        else:
            raise Http404
