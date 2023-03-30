from liiweb.settings import *  # noqa

INSTALLED_APPS = ["zimlii.apps.ZimLIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "ZimLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "ZimLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "zimlii.org"  # noqa

COURT_CODE_MAPPINGS = {
    "supreme-court-of-zimbabwe": "",
    "chinhoyi-high-court": "",
    "constitutional-court-of-zimbabwe": "",
    "harare-high-court": "",
    "bulawayo-high-court": "",
    "masvingo-high-court": "",
    "mutare-high-court": "",
    "labour-court": "",
}
