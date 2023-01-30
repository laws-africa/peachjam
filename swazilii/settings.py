from liiweb.settings import *  # noqa

INSTALLED_APPS = ["swazilii.apps.SwaziLIIConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "swazilii.urls"


JAZZMIN_SETTINGS["site_title"] = "SwaziLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "SwaziLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "swazilii.org"  # noqa
