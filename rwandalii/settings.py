from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["rwandalii.apps.RwandaLIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "RwandaLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "RwandaLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "rwandalii.laws.africa"  # noqa

LANGUAGES = [
    ("en", _("English")),
]
