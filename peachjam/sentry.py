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
import re
import tomllib
from dataclasses import dataclass
from http.cookies import CookieError, SimpleCookie
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.core.signing import BadSignature, SignatureExpired

SENTRY_SAMPLING_COOKIE_NAME = "pj_sentry_sampling"
SENTRY_SAMPLING_COOKIE_SALT = "peachjam.sentry_sampling"
SENTRY_SAMPLING_MAX_AGE = 5 * 60
SENTRY_SAMPLING_TRACE = "trace"
SENTRY_SAMPLING_PROFILE = "profile"
SENTRY_SAMPLING_MODES = {SENTRY_SAMPLING_TRACE, SENTRY_SAMPLING_PROFILE}

PEACHJAM_DEPENDENCY_RE = re.compile(
    r"peachjam(?:\[[^]]+\])?\s*@\s*"
    r"git\+https://github\.com/laws-africa/peachjam\.git@"
    r"(?P<revision>[0-9a-f]{40})(?:\s|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SentryReleaseInfo:
    """Describe the deployed application and its PeachJam dependency."""

    release: str | None
    package: str | None
    revision: str | None
    peachjam_revision: str | None

    def context(self):
        return {
            key: value
            for key, value in {
                "release": self.release,
                "package": self.package,
                "revision": self.revision,
                "peachjam_revision": self.peachjam_revision,
            }.items()
            if value
        }


def get_sentry_release_info(pyproject_path=None, environ=None):
    """Build Sentry release metadata for the application being deployed."""
    environ = os.environ if environ is None else environ
    pyproject_path = Path(pyproject_path or Path.cwd() / "pyproject.toml")
    pyproject = load_pyproject(pyproject_path)

    sentry_config = pyproject.get("tool", {}).get("peachjam", {}).get("sentry", {})
    project = pyproject.get("project", {})
    package = (
        environ.get("SENTRY_RELEASE_PACKAGE")
        or sentry_config.get("release-package")
        or project.get("name")
    )
    revision = environ.get("GIT_REV")
    release = environ.get("SENTRY_RELEASE")

    if not revision and release and package and release.startswith(f"{package}@"):
        revision = release.removeprefix(f"{package}@")
    if not release and package and revision:
        release = f"{package}@{revision}"

    peachjam_revision = environ.get("PEACHJAM_REVISION")
    if not peachjam_revision:
        if package == "peachjam":
            peachjam_revision = revision
        else:
            peachjam_revision = get_peachjam_dependency_revision(project)

    return SentryReleaseInfo(
        release=release,
        package=package,
        revision=revision,
        peachjam_revision=peachjam_revision,
    )


def get_sentry_runtime_tags(environ=None):
    """Return tags that describe the current server process."""
    environ = os.environ if environ is None else environ
    process_type = environ.get("SENTRY_PROCESS_TYPE")
    return {"process_type": process_type} if process_type else {}


def load_pyproject(path):
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except (FileNotFoundError, OSError, tomllib.TOMLDecodeError):
        return {}


def get_peachjam_dependency_revision(project):
    for dependency in project.get("dependencies", []):
        match = PEACHJAM_DEPENDENCY_RE.fullmatch(dependency.strip())
        if match:
            return match.group("revision")
    return None


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
