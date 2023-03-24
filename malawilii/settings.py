from liiweb.settings import *  # noqa

INSTALLED_APPS = ["malawilii.apps.MalawiLIIConfig"] + INSTALLED_APPS  # noqa

COURT_CODE_MAPPINGS = {}

JAZZMIN_SETTINGS["site_title"] = "MalawiLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "MalawiLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "malawilii.org"  # noqa
