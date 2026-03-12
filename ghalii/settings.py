from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["ghalii.apps.GhaLIIConfig", "peachjam_ml"] + INSTALLED_APPS  # noqa

PEACHJAM["CHAT_ENABLED"] = True  # noqa
PEACHJAM["CHAT_PUBLIC"] = True  # noqa

# turn on document embeddings for document similarity without semantic search
PEACHJAM["DOCUMENT_EMBEDDINGS"] = True  # noqa


JAZZMIN_SETTINGS["site_title"] = "GhaLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "GhaLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "ghalii.org"  # noqa

COURT_CODE_MAPPINGS = {
    "supreme-court": "GHASC",
    "court-of-appeal": "GHACA",
    "High-Court": "",
    "High-Court---Criminal": "",
    "High-Court---General-Jurisdiction": "",
    "High-Court---General-Jurisdiction-": "",
    "High-Court---Land": "",
}

LANGUAGES = [
    ("en", _("English")),
]
