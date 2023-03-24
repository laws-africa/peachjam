from liiweb.settings import *  # noqa

INSTALLED_APPS = ["lesotholii.apps.LesothoLIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "LesothoLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "LesothoLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "lesotholii.org"  # noqa

COURT_CODE_MAPPINGS = {}
