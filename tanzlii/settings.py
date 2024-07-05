from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["tanzlii.apps.TanzLIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "TanzLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "TanzLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "tanzlii.org"  # noqa

COURT_CODE_MAPPINGS = {"court-appeal-tanzania": "TZCA", "high-court-tanzania": "TZHC"}

# Custom middleware to force the I18N machinery to always choose settings.LANGUAGE_CODE
# as the default initial language, unless another one is set via sessions or cookies
# MIDDLEWARE = ["peachjam.middleware.ForceDefaultLanguageMiddleware"] + MIDDLEWARE  # noqa

# LANGUAGE_CODE = "sw"

LANGUAGES = [
    ("en", _("English")),
    ("sw", _("Swahili")),
]


if not DEBUG:  # noqa
    # Serve tanzlii-media files from CDN
    DYNAMIC_STORAGE["PREFIXES"]["s3"]["buckets"] = {  # noqa
        "tanzlii-media": {
            "custom_domain": "media.tanzlii.org",
        }
    }
