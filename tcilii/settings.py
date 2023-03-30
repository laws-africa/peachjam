from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["tcilii.apps.TCILIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "TCILII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "TCILII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "tcilii.org"  # noqa

COURT_CODE_MAPPINGS = {
    "supreme-court-of-turks-and-caicos-islands": "",
    "court-of-appeal-of-turks-and-caicos-islands": "",
    "the-judicial-committee-of-the-privy-council": "",
}
LANGUAGES = [
    ("en", _("English")),
]
