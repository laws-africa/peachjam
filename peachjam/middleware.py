import logging
import re

from django.conf import settings
from django.middleware.cache import UpdateCacheMiddleware
from django.shortcuts import redirect
from django.utils.cache import get_max_age, patch_cache_control, patch_vary_headers
from django.utils.deprecation import MiddlewareMixin

log = logging.getLogger(__name__)


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
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                request.set_language,
                max_age=settings.LANGUAGE_COOKIE_AGE,
                path=settings.LANGUAGE_COOKIE_PATH,
                domain=settings.LANGUAGE_COOKIE_DOMAIN,
                secure=settings.LANGUAGE_COOKIE_SECURE,
                httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
                samesite=settings.LANGUAGE_COOKIE_SAMESITE,
            )
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
        "/_",
        "/accounts/",
        "/admin/",
        "/api/",
        "/my/",
        "/user/",
        "/search/saved-searches/",
    ]

    lang_path_re = re.compile("^/[a-z]{2}/")

    STALE_WHILE_REVALIDATE = 120
    STALE_IF_ERROR = 600

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

            # strip language-based path
            if self.lang_path_re.match(request.path) and request.path[3:].startswith(
                prefix
            ):
                return False

        return True

    def process_response(self, request, response):
        """Set extra cache details for responses that the superclass has decided are cacheable."""
        response = super().process_response(request, response)

        if get_max_age(response) is not None and "private" not in response.get(
            "Cache-Control", ()
        ):
            # there's a max age set, even if it's zero (which is used in debug mode), so set extra caching info
            patch_cache_control(
                response,
                stale_while_revalidate=self.STALE_WHILE_REVALIDATE,
                stale_if_error=self.STALE_IF_ERROR,
                public=True,
            )
            # Remove 'Cookie' from Vary
            vary = [
                v.strip()
                for v in response.headers.get("Vary", "").split(",")
                if v.strip()
            ]
            if any(v.lower() == "cookie" for v in vary):
                keep = [v for v in vary if v.lower() != "cookie"]
                if keep:
                    response.headers["Vary"] = ", ".join(keep)
                else:
                    # No other vary headers remain
                    response.headers.pop("Vary", None)

        return response


class VaryOnHxHeadersMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        patch_vary_headers(response, ["Hx-Request", "Hx-Target"])
        return response


class SanityCheckCacheMiddleware:
    """This sanity checks that responses that are marked as cacheable are not leaking per-user information.
    It must be one of the first middleware in the stack, so that it is the last middleware to process a response.

    If response is public-cacheable:
    - forbid Set-Cookie and Vary: Cookie
    - forbid CSRF form fields in HTML
    """

    CSRF_INPUT_RE = re.compile(r'name=["\']csrfmiddlewaretoken["\']', re.I)
    # scan first N bytes of HTML
    SCAN_BYTES = getattr(settings, "CACHE_SANITY_SCAN_BYTES", 120_000)

    def __init__(self, get_response):
        self.get_response = get_response
        self.strict = getattr(settings, "CACHE_SANITY_STRICT", settings.DEBUG)

    def __call__(self, request):
        resp = self.get_response(request)

        try:
            if self.is_cacheable(resp):
                self.check_no_set_cookie(request, resp)
                self.check_no_vary_cookie(request, resp)
                self.check_no_csrf_in_html(resp)
        except AssertionError:
            raise
        except Exception as e:
            # never break prod because of sanity logic
            log.exception("CacheSanity middleware error: %s", e)

        return resp

    def is_cacheable(self, resp):
        """
        Treat as 'public cacheable' if Cache-Control allows shared caching.
        - Has 'public' without 'private'/'no-store'
        - And it's a 200/301/404 with non-streaming body (we don't scan streams)
        """
        cc = resp.headers.get("Cache-Control", "").lower()
        if not cc:
            return False
        if "no-store" in cc or "private" in cc:
            return False
        if "public" in cc:
            return True
        return False

    # --- checks ---
    def check_no_set_cookie(self, request, resp):
        sc = resp.headers.get("Set-Cookie")
        if not sc:
            return
        # Common accidental cookies that poison cache
        offenders = []
        for part in sc.split("\n"):
            name = part.split("=", 1)[0].strip().lower()
            offenders.append(name)
        self.fail(
            f"Public-cacheable response has Set-Cookie: {', '.join(offenders)} on "
            f"{request.method} {request.get_full_path()}"
        )

    def check_no_vary_cookie(self, request, resp):
        vary = resp.headers.get("Vary", "")
        if any(v.strip().lower() == "cookie" for v in vary.split(",") if v):
            self.fail(
                f"Public-cacheable response varies on Cookie: {request.method} {request.get_full_path()}"
            )

    def check_no_csrf_in_html(self, resp):
        ctype = resp.headers.get("Content-Type", "").lower()
        if "text/html" not in ctype:
            return
        if not hasattr(resp, "content"):
            return  # don't try to read streams
        try:
            sample = resp.content[: self.SCAN_BYTES].decode(errors="ignore")
        except Exception:
            return
        if self.CSRF_INPUT_RE.search(sample):
            self.fail(
                "Public-cacheable HTML includes a CSRF form input; move forms to private fragments."
            )

    def fail(self, message):
        if self.strict:
            raise AssertionError("[CacheSanity] " + message)
        log.error(f"[CacheSanity] {message}")
