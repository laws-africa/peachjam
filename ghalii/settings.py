from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["ghalii.apps.GhaLIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "GhaLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "GhaLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "ghalii.org"  # noqa

COURT_CODE_MAPPINGS = {
    "supreme-court": "GHASC",
    "court-of-appeal": "GHACA",
    "High-Court": "",
    "High-Court---Criminal": "",
    "High-Court---General-Jurisdiction": "",
    "High-Court---General-Jurisdiction-": "",
    "High-Court---Land": "",
}

LANGUAGES = [
    ("en", _("English")),
]
