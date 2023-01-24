from liiweb.settings import *  # noqa

INSTALLED_APPS = ["zambialii.apps.ZambiaLIIConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "zambialii.urls"


JAZZMIN_SETTINGS["site_title"] = "ZambiaLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "ZambiaLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "zambialii.org"  # noqa
