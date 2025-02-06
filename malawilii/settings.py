from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["malawilii.apps.MalawiLIIConfig"] + INSTALLED_APPS  # noqa


JAZZMIN_SETTINGS["site_title"] = "MalawiLII"  # noqa
JAZZMIN_SETTINGS["site_header"] = "MalawiLII"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "malawilii.org"  # noqa

COURT_CODE_MAPPINGS = {
    "supreme-court-of-appeal": "MWSC",
    "magistrate-court-blantyre": "MWMCB",
    "high-court-criminal-division": "MWHCCrim",
    "high-court-family-and-probate-division": "MWHCFam",
    "high-court-revenue-division": "MWHCRev",
    "high-court-civil-division": "MWHCCiv",
    "high-court-general-division": "MWHC",
    "high-court-commercial-division": "MWCommC",
    "industrial-relations-court": "MWIRC",
    "magistrate-court-lilongwe": "MWMCL",
    "magistrate-court-mangochi": "MWMCM",
    "magistrate-court-zomba": "MWMCZ",
}

LANGUAGES = [
    ("en", _("English")),
]


if not DEBUG:  # noqa
    # malawilii media files are stored on S3 and served via a Cloudflare CDN (via copying to R2).
    # We can therefore set long-lived cache headers and serve them from a custom domain.
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": f"max-age={86400*5}"}
    AWS_S3_CUSTOM_DOMAIN = "media.malawilii.org"
