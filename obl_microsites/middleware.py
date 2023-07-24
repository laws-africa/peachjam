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
            # TODO: falls back to CPT for debugging
            code = "cpt"
        else:
            if "." in host:
                host = host.split(".", 1)[0]
            code = {"bergrivier": "wc013"}.get(host, None)
        if not code:
            raise Http404

        request.obl_locality = get_object_or_404(Locality.objects, code=code)
        return self.get_response(request)
