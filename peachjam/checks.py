import os

from django.conf import settings
from django.core.checks import Error, register


def is_blank(value):
    return value is None or str(value).strip() == ""


@register()
def check_chat_configuration(app_configs, **kwargs):
    """Ensure that when CHAT_ENABLED is True, all required settings and environment variables are set."""
    if settings.DEBUG or not settings.PEACHJAM.get("CHAT_ENABLED"):
        return []

    errors = []

    if is_blank(settings.PEACHJAM.get("LAWSAFRICA_API_KEY")):
        errors.append(
            Error(
                'PEACHJAM["LAWSAFRICA_API_KEY"] must not be blank when CHAT_ENABLED is True.',
                id="peachjam.E001",
            )
        )

    required_env_vars = [
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_TRACING_ENVIRONMENT",
        "OPENAI_API_KEY",
    ]
    missing_env_vars = [
        env_var for env_var in required_env_vars if is_blank(os.environ.get(env_var))
    ]
    if missing_env_vars:
        errors.append(
            Error(
                f"Missing required environment variables for when CHAT_ENABLED is True: "
                f"{', '.join(missing_env_vars)}.",
                id="peachjam.E002",
            )
        )

    return errors
