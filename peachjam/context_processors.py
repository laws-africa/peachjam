from django.conf import settings

from peachjam.models.settings import pj_settings


def general(request):
    """
    Add some useful context to templates.
    """
    return {
        "DEBUG": settings.DEBUG,
        "APP_NAME": settings.PEACHJAM["APP_NAME"],
        "SUPPORT_EMAIL": settings.PEACHJAM["SUPPORT_EMAIL"],
        "SENTRY_CONFIG": {
            "dsn": settings.PEACHJAM["SENTRY_DSN_KEY"],
            "environment": settings.PEACHJAM["SENTRY_ENVIRONMENT"],
        },
        "PEACHJAM_SETTINGS": pj_settings(),
    }
