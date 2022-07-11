from django.conf import settings


def general(request):
    """
    Add some useful context to templates.
    """
    return {
        "DEBUG": settings.DEBUG,
        "APP_NAME": settings.PEACHJAM["APP_NAME"],
        "SUPPORT_EMAIL": settings.PEACHJAM["SUPPORT_EMAIL"],
        "SENTRY_DSN_KEY": settings.PEACHJAM["SENTRY_DSN_KEY"],
        "SENTRY_ENVIRONMENT": settings.PEACHJAM["SENTRY_ENVIRONMENT"],
        "GOOGLE_ANALYTICS_ID": settings.GOOGLE_ANALYTICS_ID,
    }
