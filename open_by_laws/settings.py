from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["open_by_laws.apps.OpenByLawsConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "open_by_laws.urls"
ALLOWED_HOSTS = build_allowed_hosts(  # noqa
    "openbylaws.org.za",
    "www.openbylaws.org.za",
    "bergrivier.openbylaws.org.za",
    "www.bergrivier.openbylaws.org.za",
    "capeagulhas.openbylaws.org.za",
    "www.capeagulhas.openbylaws.org.za",
    "cederberg.openbylaws.org.za",
    "www.cederberg.openbylaws.org.za",
    "matzikama.openbylaws.org.za",
    "www.matzikama.openbylaws.org.za",
    "mbizana.openbylaws.org.za",
    "www.mbizana.openbylaws.org.za",
)

MIDDLEWARE = [
    "open_by_laws.middleware.LegacyMicrositeRedirectMiddleware"
] + MIDDLEWARE  # noqa

JAZZMIN_SETTINGS["site_title"] = "Open By-laws"  # noqa
JAZZMIN_SETTINGS["site_header"] = "Open By-laws"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "openbylaws.org.za"  # noqa


TEMPLATES[0]["OPTIONS"]["context_processors"].append(  # noqa
    "open_by_laws.context_processors.open_by_laws"
)

LANGUAGES = [
    ("en", _("English")),
]

MICROSITE_REDIRECTS = {
    "bergrivier": "wc013",
    "capeagulhas": "wc033",
    "cederberg": "wc012",
    "matzikama": "wc011",
    "mbizana": "ec443",
}
