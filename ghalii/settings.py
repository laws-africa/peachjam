from liiweb.settings import *  # noqa

INSTALLED_APPS = ["ghalii.apps.GhaLIIConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "ghalii.urls"


JAZZMIN_SETTINGS["site_title"] = "GhaLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "GhaLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "ghalii.org"  # noqa
