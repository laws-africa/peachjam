from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["namiblii.apps.NamibLIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "NamibLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "NamibLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "namiblii.org"  # noqa

COURT_CODE_MAPPINGS = {
    "supreme-court": "NASC",
    "high-court-prison-division": "",
    "labour-court-northern-local-division": "",
    "high-court-main-division": "NAHCMD",
    "northern-local-division": "NAHCNLD",
    "high-court": "NAHC",
    "labour-court-main-division": "NALCMD",
    "labour-cour": "NALC",
}
LANGUAGES = [
    ("en", _("English")),
]
