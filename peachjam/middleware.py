from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin


class StripDomainPrefixMiddleware:
    """If the domain starts with a certain prefix, strip it and redirect to the new URL permanently."""

    prefix = None

    def __init__(self, get_response):
        assert self.prefix
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        host = request.get_host()
        if host and host.startswith(self.prefix):
            stripped = host[len(self.prefix) :]
            return redirect(
                f"https://{stripped}{request.get_full_path()}", permanent=True
            )

        return response


class RedirectWWWMiddleware:
    """Redirect from www.example.com to example.com"""

    prefix = "www."


class RedirectNewMiddleware:
    """Redirect from new.example.com to example.com"""

    prefix = "new."


class ForceDefaultLanguageMiddleware(MiddlewareMixin):
    """
    Ignore Accept-Language HTTP headers

    This will force the I18N machinery to always choose settings.LANGUAGE_CODE
    as the default initial language, unless another one is set via sessions or cookies.

    Should be installed *before* any middleware that checks request.META['HTTP_ACCEPT_LANGUAGE'],
    namely django.middleware.locale.LocaleMiddleware
    """

    def process_request(self, request):
        if "HTTP_ACCEPT_LANGUAGE" in request.META:
            del request.META["HTTP_ACCEPT_LANGUAGE"]
