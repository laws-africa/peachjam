from peachjam.settings import *  # noqa

INSTALLED_APPS = ["africanlii.apps.AfricanliiConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "africanlii.urls"

JAZZMIN_SETTINGS["site_title"] = "Africanlii"  # noqa
JAZZMIN_SETTINGS["site_header"] = "Africanlii"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "Agp.africanlli.org"  # noqa

PEACHJAM["EXTRA_SEARCH_INDEXES"] = [  # noqa
    "eswatinilii",
    "ghalii",
    "lawlibrary",
    "lesotholii",
    "malawilii",
    "namiblii",
    "seylii",
    "sierralii",
    "tanzlii",
    "tcilii",
    "ulii",
    "zambialii",
    "zanzibarlii",
    "zimlii",
]
PEACHJAM["SEARCH_JURISDICTION_FILTER"] = True  # noqa

# The slugs of the taxonomy roots that are treated as federated indexes
FEDERATED_DOC_INDEX_ROOTS = ["case-indexes"]

# add middleware to redirect from agp.africanlii.org to africanlii.org
MIDDLEWARE.insert(1, "africanlii.middleware.RedirectAGPMiddleware")  # noqa
