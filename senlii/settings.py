from liiweb.settings import *  # noqa

INSTALLED_APPS = ["senlii.apps.SenLIIConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "senlii.urls"


JAZZMIN_SETTINGS["site_title"] = "SenLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "SenLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "senlii.org"  # noqa
