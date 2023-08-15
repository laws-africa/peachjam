from liiweb.settings import *  # noqa

INSTALLED_APPS = ["lawlibrary.apps.LawlibraryConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "lawlibrary.urls"

JAZZMIN_SETTINGS["site_title"] = "Lawlibrary"  # noqa
JAZZMIN_SETTINGS["site_header"] = "Lawlibrary"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "Lawlibrary.org.za"  # noqa

TEMPLATES[0]["OPTIONS"]["context_processors"].append(  # noqa
    "lawlibrary.context_processors.lawlibrary"
)
