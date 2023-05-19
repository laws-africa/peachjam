from django.http import Http404
from django.views.generic.base import RedirectView

from peachjam.models.settings import PeachJamSettings


class MetabaseRedirectView(RedirectView):

    site_settings = PeachJamSettings.objects.first()

    def get_redirect_url(self, *args, **kwargs):
        self.site_settings.refresh_from_db()
        if self.site_settings.metabase_dashboard_link:
            return self.site_settings.metabase_dashboard_link
        else:
            raise Http404
