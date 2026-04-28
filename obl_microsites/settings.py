from open_by_laws.settings import *  # noqa

INSTALLED_APPS = ["obl_microsites"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "obl_microsites.urls"
ALLOWED_HOSTS = build_allowed_hosts(  # noqa
    "bergrivier.openbylaws.org.za",
    "www.bergrivier.openbylaws.org.za",
    "capeagulhas.openbylaws.org.za" "www.capeagulhas.openbylaws.org.za",
    "cederberg.openbylaws.org.za",
    "www.cederberg.openbylaws.org.za" "matzikama.openbylaws.org.za",
    "www.matzikama.openbylaws.org.za",
    "mbizana.openbylaws.org.za",
    "www.mbizana.openbylaws.org.za",
)

MIDDLEWARE = ["obl_microsites.middleware.LocalityMiddleware"] + MIDDLEWARE  # noqa

TEMPLATES[0]["OPTIONS"]["context_processors"].append(  # noqa
    "obl_microsites.context_processors.obl_microsites"
)

# rely on open-by-laws to manage search indexing
ELASTICSEARCH_DSL_AUTOSYNC = False
