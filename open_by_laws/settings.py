from liiweb.settings import *  # noqa

INSTALLED_APPS = ["open_by_laws.apps.OpenByLawsConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "open_by_laws.urls"

JAZZMIN_SETTINGS["site_title"] = "Open By-laws"  # noqa
JAZZMIN_SETTINGS["site_header"] = "Open By-laws"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "openbylaws.org.za"  # noqa


TEMPLATES[0]["OPTIONS"]["context_processors"].append(  # noqa
    "open_by_laws.context_processors.open_by_laws"
)
