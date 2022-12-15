from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["ulii.apps.ULIIConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "ulii.urls"


LANGUAGES = [
    ("sw", _("Swahili")),
    ("en", _("English")),
]


JAZZMIN_SETTINGS["site_title"] = "ULII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "ULII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "ulii.org"  # noqa
