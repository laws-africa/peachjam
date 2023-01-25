from liiweb.settings import *  # noqa

INSTALLED_APPS = ["malawilii.apps.MalawiLIIConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "malawilii.urls"


JAZZMIN_SETTINGS["site_title"] = "MalawiLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "MalawiLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "malawilii.org"  # noqa
