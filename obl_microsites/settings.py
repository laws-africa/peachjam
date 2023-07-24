from open_by_laws.settings import *  # noqa

INSTALLED_APPS = ["obl_microsites"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "obl_microsites.urls"

MIDDLEWARE = ["obl_microsites.middleware.LocalityMiddleware"] + MIDDLEWARE  # noqa

TEMPLATES[0]["OPTIONS"]["context_processors"].append(  # noqa
    "obl_microsites.context_processors.obl_microsites"
)

# rely on open-by-laws to manage search indexing
ELASTICSEARCH_DSL_AUTOSYNC = False
