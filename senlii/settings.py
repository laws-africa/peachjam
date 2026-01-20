from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["senlii.apps.SenLIIConfig", "peachjam_ml"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "senlii.urls"

LANGUAGE_CODE = "fr"

LANGUAGES = [
    ("fr", _("French")),
    ("en", _("English")),
]

# For model translation fields, ensure that English is included as a fallback. Otherwise, if the default language
# doesn't have a translation, there will be no fallback language.
MODELTRANSLATION_FALLBACK_LANGUAGES = [LANGUAGE_CODE, "en"]


JAZZMIN_SETTINGS["site_title"] = "SenegalLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "SenegalLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "senlii.org"  # noqa

PEACHJAM["MY_LII"] = f"Mon {PEACHJAM['APP_NAME']}"  # noqa
PEACHJAM["SUMMARISER_LANGUAGE"] = "French"  # noqa

PEACHJAM["CHAT_ENABLED"] = True  # noqa
PEACHJAM["CHAT_ASSISTANT_NAME"] = "l'IA"  # noqa
