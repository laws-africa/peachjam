from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["mauritiuslii.apps.MauritiusLIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "MauritiusLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "MauritiusLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "mauritiuslii.laws.africa"  # noqa

LANGUAGES = [
    ("en", _("English")),
]
