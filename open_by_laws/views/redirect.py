from django.views.generic import RedirectView


class RedirectOldPlaceCodesView(RedirectView):
    """
    A view to redirect old place codes to new place codes
    """

    def get_redirect_url(self, place_code, *args, **kwargs):
        return f"/bylaws/{place_code}"
