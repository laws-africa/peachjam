from django.conf import settings
from django.http import HttpResponseNotFound, HttpResponsePermanentRedirect
from django.utils.deprecation import MiddlewareMixin


class RedirectMiddleware(MiddlewareMixin):
    """Middleware that redirects requests to:

        - the legacy archive.gazettes.laws.africa
        - www.gazettes.africa

    to gazettes.africa.
    """

    def process_request(self, request):
        host = request.get_host()
        if host in ["archive.gazettes.laws.africa", "www.gazettes.africa"]:
            uri = f"https://gazettes.africa{request.get_full_path()}"
            return HttpResponsePermanentRedirect(uri)


class NoIPMiddleware(MiddlewareMixin):
    """Middleware that forces a 404 for an request that does not use a
    domain name.

    We use this because otherwise Google indexes the gazettes archive using
    the IP of the server, for some odd reason.

    Note that during deployment, the dokku aliveness check comes from a local host
    with an ip, but with ':5000'
    """

    def process_request(self, request):
        host = request.get_host()
        if (
            not settings.DEBUG
            and "africa" not in host
            and "localhost" not in host
            and not host.endswith(":5000")
        ):
            return HttpResponseNotFound("not found")
