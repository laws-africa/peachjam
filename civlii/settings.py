from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["civlii.apps.CIVLIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "CIVLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "CIVLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "civlii.laws.africa"  # noqa

LANGUAGES = [
    ("fr", _("French")),
    ("en", _("English")),
]
LANGUAGE_CODE = "fr"

PEACHJAM["MY_LII"] = f"Mon {PEACHJAM['APP_NAME']}"  # noqa
