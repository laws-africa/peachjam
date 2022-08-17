from liiweb.settings import *  # noqa

INSTALLED_APPS = [
    "lawlibrary.apps.LawlibraryConfig",
    "lawlibrary_api.apps.LawlibraryApiConfig",
] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "lawlibrary.urls"
