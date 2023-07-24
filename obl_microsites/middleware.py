from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404

from peachjam.models import Locality


class LocalityMiddleware(object):
    """Middleware to determine the locality for the microsite, based on the domain of the request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host()

        if host.startswith("127.0.0.1") or host.startswith("localhost"):
            host = "bergrivier"
        elif "." in host:
            host = host.split(".", 1)[0]

        microsite = settings.MICROSITES.get(host)
        if not microsite:
            raise Http404

        if "locality" not in microsite:
            microsite["locality"] = get_object_or_404(
                Locality.objects, code=microsite["code"]
            )
        request.microsite = microsite
        return self.get_response(request)
