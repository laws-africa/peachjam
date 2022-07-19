from peachjam.settings import *  # noqa

ROOT_URLCONF = "peachjam.urls"

INSTALLED_APPS = ["africanlii.apps.AfricanliiConfig"] + INSTALLED_APPS  # noqa
