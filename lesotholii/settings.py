from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["lesotholii.apps.LesothoLIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "LesothoLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "LesothoLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "lesotholii.org"  # noqa

COURT_CODE_MAPPINGS = {
    "court-of-appeal": "",
    "high-court": "",
    "high-court-commercial-division": "",
    "high-court-constitutional-division": "",
    "high-court-land-division": "",
    "labour-appeal-court": "",
    "labour-court": "",
}
LANGUAGES = [
    ("en", _("English")),
]
