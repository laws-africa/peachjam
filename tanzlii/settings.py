from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["tanzlii.apps.TanzLIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "TanzLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "TanzLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "tanzlii.org"  # noqa

COURT_CODE_MAPPINGS = {"court-appeal-tanzania": "TZCA", "high-court-tanzania": "TZHC"}
LANGUAGE_CODE = "sw"

LANGUAGES = [
    ("en", _("English")),
    ("sw", _("Swahili")),
]
