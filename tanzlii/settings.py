from liiweb.settings import *  # noqa

INSTALLED_APPS = ["tanzlii.apps.TanzLIIConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "tanzlii.urls"


JAZZMIN_SETTINGS["site_title"] = "TanzLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "TanzLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "tanzlii.org"  # noqa
