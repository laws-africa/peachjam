from liiweb.settings import *  # noqa

INSTALLED_APPS = [
    "lawlibrary.apps.LawlibraryConfig",
    "peachjam_subs",
    "peachjam_ml",
] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "lawlibrary.urls"

JAZZMIN_SETTINGS["site_title"] = "Lawlibrary"  # noqa
JAZZMIN_SETTINGS["site_header"] = "Lawlibrary"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "Lawlibrary.org.za"  # noqa

PEACHJAM["MULTIPLE_LOCALITIES"] = True  # noqa


TEMPLATES[0]["OPTIONS"]["context_processors"].append(  # noqa
    "lawlibrary.context_processors.lawlibrary"
)


if not DEBUG:  # noqa
    # Law Library media files are stored on S3 and served via a Cloudflare CDN (via copying to R2).
    # We can therefore set long-lived cache headers and serve them from a custom domain.
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": f"max-age={86400*5}"}
    AWS_S3_CUSTOM_DOMAIN = "media.lawlibrary.org.za"
