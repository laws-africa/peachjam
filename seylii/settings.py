from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["seylii.apps.SeyLIIConfig"] + INSTALLED_APPS  # noqa


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
