from django.views.generic import RedirectView


class RedirectOldPlaceCodesView(RedirectView):
    """
    A view to redirect old place codes to new place codes
    e.g. /za-cpt/eng/ -> /bylaws/cpt/
    """

    def get_redirect_url(self, place_code, *args, **kwargs):
        return f"/bylaws/{place_code}"


class RedirectByLawView(RedirectView):
    """
    A view to redirect old by-law detail pages to new by-law detail pages
    e.g. /za-cpt/act/by-law/2016/air-quality-management/eng/ -> /akn/za-cpt/act/by-law/2016/air-quality-management/
    """

    def get_redirect_url(self, path, language, *args, **kwargs):
        original_path = self.request.path
        if original_path.endswith(f"/{language}/"):
            redirect_path = "/akn/" + original_path.strip(f"/{language}/")
        return redirect_path
