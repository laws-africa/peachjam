from django.conf import settings
from django.templatetags.static import static

from peachjam.models.settings import pj_settings


def general(request):
    """
    Add some useful context to templates.
    """
    # get current language
    language = getattr(request, "LANGUAGE_CODE", settings.LANGUAGE_CODE)

    return {
        "DEBUG": settings.DEBUG,
        "APP_NAME": settings.PEACHJAM["APP_NAME"],
        "SUPPORT_EMAIL": settings.PEACHJAM["SUPPORT_EMAIL"],
        "PEACHJAM_SETTINGS": pj_settings(),
        "CURRENT_LANGUAGE": language,
        "MULTIPLE_JURISDICTIONS": settings.PEACHJAM["MULTIPLE_JURISDICTIONS"],
        "MULTIPLE_LOCALITIES": settings.PEACHJAM["MULTIPLE_LOCALITIES"],
        # this object will be injected into Javascript to provide configuration settings to the Javascript app
        "PEACHJAM_JS_CONFIG": {
            "appName": settings.PEACHJAM["APP_NAME"],
            "pdfWorker": static("js/pdf.worker-prod.js"),
            "userHelpLink": pj_settings().user_help_link,
            "sentry": {
                "dsn": settings.PEACHJAM["SENTRY_DSN_KEY"],
                "environment": settings.PEACHJAM["SENTRY_ENVIRONMENT"],
            },
        },
    }
