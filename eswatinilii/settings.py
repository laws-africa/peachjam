from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["eswatinilii.apps.EswatiniLIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "EswatiniLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "EswatiniLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "eswatinilii.org"  # noqa

COURT_CODE_MAPPINGS = {}

LANGUAGES = [
    ("en", _("English")),
]
