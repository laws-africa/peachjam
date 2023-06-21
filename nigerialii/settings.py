from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["nigerialii.apps.NigeriaLIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "NigeriaLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "NigeriaLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "nigerialii.org"  # noqa


LANGUAGES = [
    ("en", _("English")),
]
