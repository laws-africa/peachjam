from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["ulii.apps.ULIIConfig"] + INSTALLED_APPS  # noqa


LANGUAGES = [
    ("sw", _("Swahili")),
    ("en", _("English")),
]


JAZZMIN_SETTINGS["site_title"] = "ULII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "ULII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "ulii.org"  # noqa

COURT_CODE_MAPPINGS = {
    "leadership-code-tribunal-uganda": "UGLCT",
    "supreme-court-uganda": "UGSC",
    "court-appeal-uganda": "UGCA",
    "constitutional-court-uganda": "UGCC",
    "commercial-court-uganda": "UGCommC",
    "industrial-court-uganda": "UGIC",
    "high-court-uganda": "UGHC",
    "hc-civil-division-uganda": "UGHCCD",
    "hc-criminal-division-uganda": "UGHCCRD",
    "hc-family-division-uganda": "UGHCFD",
    "hc-land-division-uganda": "UGHCLD",
    "hc-international-crimes-division-uganda": "UGHICD",
    "hc-anti-corruption-division-uganda": "UGHCACD",
    "high-court-execution-bailiffs-division-uganda": "UGHCEBD",
    "election-petitions-uganda": "UGHCEP",
    "equal-opportunities-commission": "UGEOC",
    "center-arbitration-dispute-resolution-uganda": "UGCADER",
    "tax-appeals-tribunal-uganda": "UGTAT",
}
