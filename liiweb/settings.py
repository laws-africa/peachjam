from peachjam.settings import *  # noqa

INSTALLED_APPS = ["liiweb.apps.LiiwebConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "liiweb.urls"

# Court codes mappings for legacy lii urls
# Override this in the lii settings.py
COURT_CODE_MAPPINGS = {}

ADMINS = [("Laws.Africa", "info@laws.africa")]
