from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["zanzibarlii.apps.ZanzibarLIIConfig"] + INSTALLED_APPS  # noqa


# Custom middleware to force the I18N machinery to always choose settings.LANGUAGE_CODE
# as the default initial language, unless another one is set via sessions or cookies
MIDDLEWARE = ["peachjam.middleware.ForceDefaultLanguageMiddleware"] + MIDDLEWARE  # noqa

LANGUAGE_CODE = "sw"

LANGUAGES = [
    ("sw", _("Swahili")),
    ("en", _("English")),
]


JAZZMIN_SETTINGS["site_title"] = "ZanzibarLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "ZanzibarLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "zanzibarlii.org"  # noqa

COURT_CODE_MAPPINGS = {
    "high-court-main-registry": "TZZNZHC",
    "industrial-court": "ZIC",
    "commercial-court": "ZCC",
    "kadhi's-court": "ZKC",
}
