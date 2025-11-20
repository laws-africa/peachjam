import logging
import re
from urllib.parse import urlencode

from django.conf import settings
from django.middleware.cache import UpdateCacheMiddleware
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse
from django.utils.cache import get_max_age, patch_cache_control, patch_vary_headers
from django.utils.deprecation import MiddlewareMixin

from peachjam.models import UserProfile

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


class TermsAcceptanceMiddleware:
    """Ensure authenticated users accept the terms of use before using the site."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_url_names = {
            "account_accept_terms",
            "account_login",
            "account_logout",
            "account_signup",
            "account_reset_password",
            "account_reset_password_done",
            "account_reset_password_from_key",
            "account_reset_password_from_key_done",
            "account_change_password",
            "account_change_password_done",
            "terms_of_use",
            "csrf_token",
            "home_page",
        }
        self.exempt_namespaces = {"socialaccount"}
        self.exempt_prefixes = tuple(
            prefix
            for prefix in (
                getattr(settings, "STATIC_URL", None),
                "/favicon.ico",
                "/robots.txt",
            )
            if prefix
        )

    def __call__(self, request):
        if self._should_redirect(request):
            return self._redirect(request)
        return self.get_response(request)

    def _should_redirect(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        if request.method == "OPTIONS":  # allow pre-flight requests
            return False

        if self._is_exempt(request):
            return False

        try:
            profile = user.userprofile
        except UserProfile.DoesNotExist:
            return True

        return not getattr(profile, "accepted_terms_at", None)

    def _is_exempt(self, request):
        path = request.path

        if request.headers.get("HX-Request") == "true":
            # HTMX requests are exempt
            return True

        for prefix in self.exempt_prefixes:
            if path.startswith(prefix):
                return True

        try:
            match = resolve(path)
        except Resolver404:
            return False

        if match.url_name in self.exempt_url_names:
            return True

        if match.namespace and match.namespace.split(":")[0] in self.exempt_namespaces:
            return True

        return False

    def _redirect(self, request):
        accept_url = reverse("account_accept_terms")
        next_url = request.get_full_path()
        if next_url == accept_url:
            return redirect(accept_url)

        params = {"next": next_url} if next_url else None
        if params:
            accept_url = f"{accept_url}?{urlencode(params)}"
        return redirect(accept_url)


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

        has_nocache_param = "nocache" in request.GET

        if (
            get_max_age(response) is not None
            and "private" not in response.get("Cache-Control", ())
            and not has_nocache_param
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


class UserIDHeaderMiddleware:
    """Adds the user id to the response headers, for logging (and stripping) by nginx."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            response["X-UID"] = f"user-{request.user.userprofile.tracking_id}"
        return response
