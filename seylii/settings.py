import os

from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

TIME_ZONE = "Indian/Mahe"

INSTALLED_APPS = ["seylii.apps.SeyLIIConfig"] + INSTALLED_APPS  # noqa
MIDDLEWARE = ["peachjam.middleware.BasicAuthMiddleware"] + MIDDLEWARE  # noqa

ALLOWED_HOSTS = build_allowed_hosts("seylii.laws.africa")  # noqa

BASIC_AUTH_USERNAME = os.environ.get("BASIC_AUTH_USERNAME", "")
BASIC_AUTH_PASSWORD = os.environ.get("BASIC_AUTH_PASSWORD", "")
BASIC_AUTH_REALM = "Restricted"
BASIC_AUTH_EXCLUDED_PATH_PREFIXES = ["/api/", "/admin/"]

JAZZMIN_SETTINGS["site_title"] = "SeyLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "SeyLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "seylii.org"  # noqa

COURT_CODE_MAPPINGS = {
    "constitutional-court": "SCCC",
    "court-of-appeal": "SCCA",
    "court-appeal": "SCCA",
    "supreme-court": "SCSC",
}
LANGUAGES = [
    ("en", _("English")),
]
