from django.middleware.cache import UpdateCacheMiddleware
from django.shortcuts import redirect
from django.utils.cache import get_max_age, patch_vary_headers
from django.utils.deprecation import MiddlewareMixin
from django.views.i18n import set_language


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


class RedirectWWWMiddleware(StripDomainPrefixMiddleware):
    """Redirect from www.example.com to example.com"""

    prefix = "www."


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


class SetPreferredLanguageMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if hasattr(request, "set_language"):
            request.POST = {"language": request.set_language}
            response = set_language(request)
        return response


class GeneralUpdateCacheMiddleware(UpdateCacheMiddleware):
    """Custom caching for peachjam. Goals:

    1. cache most pages, because content doesn't change that much
    2. when content does change (eg. new judgments that should be shown on the homepage), reflect those ASAP
    3. staff users who change content should see updates immediately.
    4. an anonymous user who logs in should see fresh content

    Views that have their own caching logic aren't changed. Views that don't have caching enabled and don't
    opt-out of caching will be cached.

    Views can opt-out by:

    1. setting request._cache_update_cache = False OR
    2. using the Django never_cache() decorator
    """

    # url prefixes that should never be cached
    never_cache_prefixes = [
        "/admin/",
        "/accounts/",
        "/api/",
        "/saved-documents/",
        "/_",
    ]

    def _should_update_cache(self, request, response):
        if (
            hasattr(request, "_cache_update_cache")
            and request._cache_update_cache is False
        ):
            # page has opted out
            return False

        for prefix in self.never_cache_prefixes:
            if request.path.startswith(prefix):
                return False

        # support never_cache and explicit page cache times
        max_age = get_max_age(response)
        if max_age is not None:
            return False

        # anonymous and non-staff users should see cached content
        return getattr(request, "user", None) is not None and (
            request.user.is_anonymous or not request.user.is_staff
        )


class VaryOnHxHeadersMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        patch_vary_headers(response, ["Hx-Request", "Hx-Target"])
        return response
