from peachjam.settings import *  # noqa

INSTALLED_APPS = ["africanlii.apps.AfricanliiConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "africanlii.urls"

JAZZMIN_SETTINGS["site_title"] = "Africanlii"  # noqa
JAZZMIN_SETTINGS["site_header"] = "Africanlii"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "Agp.africanlli.org"  # noqa
