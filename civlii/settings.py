from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["civlii.apps.CIVLIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "CIVLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "CIVLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "civlii.laws.africa"  # noqa

LANGUAGES = [
    ("fr", _("French")),
    ("en", _("English")),
]
LANGUAGE_CODE = "fr"

# For model translation fields, ensure that English is included as a fallback. Otherwise, if the default language
# doesn't have a translation, there will be no fallback language.
MODELTRANSLATION_FALLBACK_LANGUAGES = [LANGUAGE_CODE, "en"]

PEACHJAM["MY_LII"] = f"Mon {PEACHJAM['APP_NAME']}"  # noqa
