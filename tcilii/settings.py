from liiweb.settings import *  # noqa

INSTALLED_APPS = ["tcilii.apps.TCILIIConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "tcilii.urls"


JAZZMIN_SETTINGS["site_title"] = "TCILII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "TCILII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "tcilii.org"  # noqa
