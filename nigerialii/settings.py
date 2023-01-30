from liiweb.settings import *  # noqa

INSTALLED_APPS = ["nigerialii.apps.NigeriaLIIConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "nigerialii.urls"


JAZZMIN_SETTINGS["site_title"] = "NigeriaLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "NigeriaLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "nigerialii.org"  # noqa
