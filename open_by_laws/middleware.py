from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class LegacyMicrositeRedirectMiddleware(object):
    """Redirect legacy microsite hosts to the central Open By-laws site."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(":", 1)[0].lower()

        if host.startswith("www."):
            host = host.split(".", 2)[1]
        elif "." in host:
            host = host.split(".", 1)[0]

        code = settings.MICROSITE_REDIRECTS.get(host)
        if not code:
            return self.get_response(request)

        path = request.get_full_path()
        if request.path == "/":
            path = f"/za-{code}/eng/"
            if request.META.get("QUERY_STRING"):
                path = f"{path}?{request.META['QUERY_STRING']}"

        return HttpResponsePermanentRedirect(f"https://openbylaws.org.za{path}")
