from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["zanzibarlii.apps.ZanzibarLIIConfig"] + INSTALLED_APPS  # noqa


LANGUAGES = [
    ("sw", _("Swahili")),
    ("en", _("English")),
]


JAZZMIN_SETTINGS["site_title"] = "ZanzibarLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "ZanzibarLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "zanzibarlii.org"  # noqa
