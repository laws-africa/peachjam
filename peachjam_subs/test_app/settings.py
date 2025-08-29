from liiweb.settings import *  # noqa

INSTALLED_APPS = [
    "peachjam_subs.test_app",
    "django_fsm",
    "peachjam_subs",
] + INSTALLED_APPS  # noqa
