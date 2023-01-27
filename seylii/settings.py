from liiweb.settings import *  # noqa

INSTALLED_APPS = ["seylii.apps.SeyLIIConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "seylii.urls"


JAZZMIN_SETTINGS["site_title"] = "SeyLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "SeyLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "seylii.org"  # noqa
