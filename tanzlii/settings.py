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
    # Tanzlii media files are stored on S3 and served via a Cloudflare CDN (via copying to R2).
    # We can therefore set long-lived cache headers and serve them from a custom domain.
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=31536000"}
    AWS_S3_CUSTOM_DOMAIN = "media.tanzlii.org"
