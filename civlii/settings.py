from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["civlii.apps.CIVLIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "CIVLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "CIVLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "civlii.laws.africa"  # noqa

LANGUAGES = [
    ("en", _("English")),
    ("fr", _("French")),
]
