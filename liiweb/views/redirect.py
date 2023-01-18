from django.conf import settings
from django.views.generic import RedirectView


class RedirectCaseURLsView(RedirectView):
    """
    A view to redirect legacy Lii Case URLs to new /akn/ peachjam urls.
    We can map the court code from the old url and use the serial number
    to get a work_frbr_uri, then redirect to the appropriate document,
    if available
    """

    def get_redirect_url(self, country, court, year, number, *args, **kwargs):
        court_code = settings.COURT_CODE_MAPPINGS.get(court, "")
        frbr_uri = f"/akn/{country}/judgment/{court_code.lower()}/{year}/{number}"
        return frbr_uri
