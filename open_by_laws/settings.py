from django.utils.translation import gettext_lazy as _

from liiweb.settings import *  # noqa

INSTALLED_APPS = ["open_by_laws.apps.OpenByLawsConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "open_by_laws.urls"

JAZZMIN_SETTINGS["site_title"] = "Open By-laws"  # noqa
JAZZMIN_SETTINGS["site_header"] = "Open By-laws"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "openbylaws.org.za"  # noqa


TEMPLATES[0]["OPTIONS"]["context_processors"].append(  # noqa
    "open_by_laws.context_processors.open_by_laws"
)

LANGUAGES = [
    ("en", _("English")),
]

MICROSITES = {
    "bergrivier": {
        "name": "Bergrivier",
        "code": "wc013",
        "website": "https://www.bergmun.org.za/",
        "url": "https://bergrivier.openbylaws.org.za",
    },
    "capeagulhas": {
        "name": "Cape Agulhas",
        "code": "wc033",
        "website": "https://capeagulhas.gov.za/",
        "url": "https://capeagulhas.openbylaws.org.za",
    },
    "cederberg": {
        "name": "Cederberg",
        "code": "wc012",
        "website": "http://www.cederbergmun.gov.za/",
        "url": "https://cederberg.openbylaws.org.za",
    },
    "mbizana": {
        "name": "Mbizana",
        "code": "ec443",
        "website": "http://www.mbizana.gov.za/",
        "url": "https://mbizana.openbylaws.org.za",
    },
    "matzikama": {
        "name": "Matzikama",
        "code": "wc011",
        "website": "https://www.matzikamamunicipality.co.za/",
        "url": "https://matzikama.openbylaws.org.za",
    },
}
