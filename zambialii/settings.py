from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["zambialii.apps.ZambiaLIIConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "zambialii.urls"

JAZZMIN_SETTINGS["site_title"] = "ZambiaLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "ZambiaLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "zambialii.org"  # noqa

COURT_CODE_MAPPINGS = {
    "supreme-court-of-zambia": "ZMSC",
    "subordinate-court-of-zambia": "ZMSUB",
    "local-government-election-tribunal-lusaka": "ZMLGEL",
    "court-of-appeal-of-zambia": "ZMCA",
    "constitutional-court-of-zambia": "ZMCC",
    "high-court-of-zambia": "ZMHC",
    "high-court-of-northern-rhodesia": "ZMHCNR",
    "industrial-relations-court-of-zambia": "ZMIC",
}
LANGUAGES = [
    ("en", _("English")),
]


if not DEBUG:  # noqa
    # zambialii media files are stored on S3 and served via a Cloudflare CDN (via copying to R2).
    # We can therefore set long-lived cache headers and serve them from a custom domain.
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": f"max-age={86400*5}"}
    AWS_S3_CUSTOM_DOMAIN = "media.zambialii.org"
