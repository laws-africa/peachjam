from django.http import Http404
from django.views.generic.base import RedirectView

from peachjam.models.settings import pj_settings


class MetabaseRedirectView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):

        if pj_settings().metabase_dashboard_link:
            return pj_settings().metabase_dashboard_link
        else:
            raise Http404
