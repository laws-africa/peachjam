from django.conf import settings
from django.templatetags.static import static

from peachjam.models.settings import pj_settings


def general(request):
    """
    Add some useful context to templates.
    """
    return {
        "DEBUG": settings.DEBUG,
        "APP_NAME": settings.PEACHJAM["APP_NAME"],
        "SUPPORT_EMAIL": settings.PEACHJAM["SUPPORT_EMAIL"],
        "PEACHJAM_SETTINGS": pj_settings(),
        # this object will be injected into Javascript to provide configuration settings to the Javascript app
        "PEACHJAM_JS_CONFIG": {
            "appName": settings.PEACHJAM["APP_NAME"],
            "pdfWorker": static("js/pdf.worker-prod.js"),
            "sentry": {
                "dsn": settings.PEACHJAM["SENTRY_DSN_KEY"],
                "environment": settings.PEACHJAM["SENTRY_ENVIRONMENT"],
            },
        },
    }
