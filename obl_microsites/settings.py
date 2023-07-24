from open_by_laws.settings import *  # noqa

INSTALLED_APPS = ["obl_microsites"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "obl_microsites.urls"

MIDDLEWARE = ["obl_microsites.middleware.LocalityMiddleware"] + MIDDLEWARE  # noqa

TEMPLATES[0]["OPTIONS"]["context_processors"].append(  # noqa
    "obl_microsites.context_processors.obl_microsites"
)

MICROSITES = {
    "bergrivier": {
        "code": "wc013",
        "website": "https://www.bergmun.org.za/",
    },
    "capeagulhas": {
        "code": "wc033",
        "website": "https://capeagulhas.gov.za/",
    },
    "cederberg": {
        "code": "wc012",
        "website": "http://www.cederbergmun.gov.za/",
    },
    "mbizana": {
        "code": "ec443",
        "website": "http://www.mbizana.gov.za/",
    },
    "matzikama": {
        "code": "wc011",
        "website": "https://www.matzikamamunicipality.co.za/",
    },
}

# rely on open-by-laws to manage search indexing
ELASTICSEARCH_DSL_AUTOSYNC = False
