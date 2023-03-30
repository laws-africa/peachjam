from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["zambialii.apps.ZambiaLIIConfig"] + INSTALLED_APPS  # noqa

JAZZMIN_SETTINGS["site_title"] = "ZambiaLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "ZambiaLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "zambialii.org"  # noqa

COURT_CODE_MAPPINGS = {
    "supreme-court-of-zambia": "ZMSC",
    "subordinate-court-of-zambia": "ZMSUB",
    "local-government-election-tribunal-lusaka": "ZMLGEL",
    "court-of-appeal-of-zambia": "ZMCA",
    "constitutional-court-of-zambia": "ZMCC",
    "high-court-of-zambia": "ZMHC",
    "high-court-of-northern-rhodesia": "ZMHCNR",
    "industrial-relations-court-of-zambia": "ZMIC",
}
LANGUAGES = [
    ("en", _("English")),
]
