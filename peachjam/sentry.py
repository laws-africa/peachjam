"""
Helpers for staff-triggered Sentry tracing and profiling.

Sentry decides whether to keep a request transaction at the start of the WSGI
request, before Django middleware has built a normal authenticated request. This
means the sampler cannot safely check ``request.user.is_staff`` directly.

Instead, a staff-only Django view issues a short-lived signed cookie. The Sentry
samplers read that cookie from the WSGI environ and force sampling while it is
valid:

- ``trace`` forces transaction tracing for five minutes.
- ``profile`` forces both tracing and transaction profiling for five minutes,
  because Sentry profiles are attached to sampled transactions.

The dynamic user menu uses the same cookie parser via ``request.COOKIES`` so it
can show a checkmark for the active mode.
"""

import os
from http.cookies import CookieError, SimpleCookie

from django.conf import settings
from django.core import signing
from django.core.signing import BadSignature, SignatureExpired

SENTRY_SAMPLING_COOKIE_NAME = "pj_sentry_sampling"
SENTRY_SAMPLING_COOKIE_SALT = "peachjam.sentry_sampling"
SENTRY_SAMPLING_MAX_AGE = 5 * 60
SENTRY_SAMPLING_TRACE = "trace"
SENTRY_SAMPLING_PROFILE = "profile"
SENTRY_SAMPLING_MODES = {SENTRY_SAMPLING_TRACE, SENTRY_SAMPLING_PROFILE}


def get_sentry_sampling_mode_from_request(request):
    return _get_sentry_sampling_mode_from_cookie(
        request.COOKIES.get(SENTRY_SAMPLING_COOKIE_NAME)
    )


def get_sentry_sampling_mode_from_wsgi_environ(environ):
    cookie_header = environ.get("HTTP_COOKIE", "")
    if not cookie_header:
        return None

    cookie = SimpleCookie()
    try:
        cookie.load(cookie_header)
    except CookieError:
        return None
    morsel = cookie.get(SENTRY_SAMPLING_COOKIE_NAME)
    return _get_sentry_sampling_mode_from_cookie(morsel.value if morsel else None)


def issue_sentry_sampling_cookie(response, mode):
    if mode not in SENTRY_SAMPLING_MODES:
        raise ValueError(f"Unknown Sentry sampling mode: {mode}")

    response.set_cookie(
        SENTRY_SAMPLING_COOKIE_NAME,
        signing.dumps({"mode": mode}, salt=SENTRY_SAMPLING_COOKIE_SALT),
        max_age=SENTRY_SAMPLING_MAX_AGE,
        path="/",
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="Lax",
    )


def sentry_traces_sampler(sampling_context):
    mode = _get_sentry_sampling_mode_from_sampling_context(sampling_context)
    if mode in SENTRY_SAMPLING_MODES:
        return 1.0

    return _env_sample_rate("SENTRY_SAMPLE_RATE", 0.1)


def sentry_profiles_sampler(sampling_context):
    mode = _get_sentry_sampling_mode_from_sampling_context(sampling_context)
    if mode == SENTRY_SAMPLING_PROFILE:
        return 1.0

    return _env_sample_rate("SENTRY_PROFILE_SAMPLE_RATE", 0.0)


def _get_sentry_sampling_mode_from_cookie(cookie_value):
    if not cookie_value:
        return None

    try:
        data = signing.loads(
            cookie_value,
            salt=SENTRY_SAMPLING_COOKIE_SALT,
            max_age=SENTRY_SAMPLING_MAX_AGE,
        )
    except (BadSignature, SignatureExpired):
        return None

    mode = data.get("mode") if isinstance(data, dict) else None
    return mode if mode in SENTRY_SAMPLING_MODES else None


def _get_sentry_sampling_mode_from_sampling_context(sampling_context):
    environ = sampling_context.get("wsgi_environ")
    if not environ:
        custom_context = sampling_context.get("custom_sampling_context") or {}
        environ = custom_context.get("wsgi_environ")

    if not environ:
        return None

    return get_sentry_sampling_mode_from_wsgi_environ(environ)


def _env_sample_rate(name, default):
    return float(os.environ.get(name, str(default)))
