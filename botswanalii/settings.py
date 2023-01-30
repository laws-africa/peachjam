from liiweb.settings import *  # noqa

INSTALLED_APPS = ["botswanalii.apps.BostwanaLIIConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "botswanalii.urls"


JAZZMIN_SETTINGS["site_title"] = "BotswanaLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "BotswanaLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "botswanalii.org"  # noqa
