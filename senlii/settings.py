from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["senlii.apps.SenLIIConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "senlii.urls"


LANGUAGES = [
    ("fr", _("French")),
    ("en", _("English")),
]


JAZZMIN_SETTINGS["site_title"] = "SenLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "SenLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "senlii.org"  # noqa
