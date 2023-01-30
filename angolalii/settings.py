from liiweb.settings import *  # noqa

INSTALLED_APPS = ["angolalii.apps.AngolaLIIConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "angolalii.urls"


JAZZMIN_SETTINGS["site_title"] = "AngolaLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "AngolaLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "angolalii.org"  # noqa
