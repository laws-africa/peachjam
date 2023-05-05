from peachjam.settings import *  # noqa

INSTALLED_APPS = ["africanlii.apps.AfricanliiConfig"] + INSTALLED_APPS  # noqa

ROOT_URLCONF = "africanlii.urls"

JAZZMIN_SETTINGS["site_title"] = "Africanlii"  # noqa
JAZZMIN_SETTINGS["site_header"] = "Africanlii"  # noqa
JAZZMIN_SETTINGS["site_brand"] = "Agp.africanlli.org"  # noqa

EXTRA_SEARCH_INDEXES = [
    "ghalii",
    "lawlibrary",
    "lesotholii",
    "malawilii",
    "namiblii",
    "senlii",
    "seylii",
    "sierralii",
    "tanzlii",
    "tcilii",
    "ulii",
    "zambialii",
    "zanzibarlii",
    "zimlii",
]

# The slugs of the taxonomy roots that are treated as federated indexes
FEDERATED_DOC_INDEX_ROOTS = ["case-index"]
