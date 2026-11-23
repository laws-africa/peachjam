from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

TIME_ZONE = "Africa/Lusaka"

INSTALLED_APPS = ["zambialii.apps.ZambiaLIIConfig"] + INSTALLED_APPS  # noqa

PEACHJAM["CHAT_ENABLED"] = True  # noqa

ROOT_URLCONF = "zambialii.urls"
ALLOWED_HOSTS = build_allowed_hosts("zambialii.org", "www.zambialii.org")  # noqa

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


R2_DOWNLOAD_BUCKETS = {**R2_DOWNLOAD_BUCKETS, "zambialii-files": "zambialii-files"}  # noqa: F405

if not DEBUG:  # noqa
    # Allow downloaded media to be cached by the browser.
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": f"max-age={86400 * 5}"}
