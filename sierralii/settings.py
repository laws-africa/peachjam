from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["sierralii.apps.SierraLIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "SierraLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "SierraLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "sierralii.org"  # noqa

COURT_CODE_MAPPINGS = {
    "supreme-court": "SLSC",
    "court-of-appeal": "SLCA",
    "high-court": "SLHC",
    "hc%3a-general-and-civil-division": "SLHCGD",
    "hc%3a-criminal-division": "SLHCCrD",
    "hc%3a-family-and-probate-division": "SLHCFPD",
    "hc%3a-fast-track-commercial-and-admiralty-division": "SLHCFTCAD",
    "hc%3a-industrial-and-social-security-division": "SLHCISSD",
    "hc%3a-land-and-property-and-environmental-division": "SLHCLPED",
    "hc%3a-anti-corruption-division": "",
    "hc%3a-sexual-offenses-division": "SLHCSOD",
    "special-court-for-sierra-leone": "SCSL",
}
LANGUAGES = [
    ("en", _("English")),
]
