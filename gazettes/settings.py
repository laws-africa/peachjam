from peachjam.settings import *  # noqa

# Application definition
INSTALLED_APPS = [
    "gazettes",
] + INSTALLED_APPS  # noqa


MIDDLEWARE = [
    "gazettes.middleware.RedirectMiddleware",
    "gazettes.middleware.NoIPMiddleware",
    "allauth.account.middleware.AccountMiddleware",
] + MIDDLEWARE  # noqa


# allow cross-site access from all secure origins
CORS_ALLOWED_ORIGIN_REGEXES = [r"^https://.*"]
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = r"^.*$"


ROOT_URLCONF = "gazettes.urls"


# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases
default_db_url = "postgres://gazettes:gazettes@localhost:5432/gazettes"
db_config = dj_database_url.config(  # noqa
    default=os.environ.get("DATABASE_URL", default_db_url)  # noqa
)
DATABASES["default"] = db_config  # noqa


SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

X_FRAME_OPTIONS = "SAMEORIGIN"


LANGUAGES = [
    ("en", "English"),
]


PEACHJAM["APP_NAME"] = "Gazettes.Africa"  # noqa
PEACHJAM["ES_INDEX"] = "gazettemachine"  # noqa
PEACHJAM["SEARCH_JURISDICTION_FILTER"] = True  # noqa
PEACHJAM["MULTIPLE_JURISDICTIONS"] = True  # noqa


TEMPLATES[0]["OPTIONS"]["context_processors"].append(  # noqa
    "gazettes.context_processors.jurisdictions"
)
