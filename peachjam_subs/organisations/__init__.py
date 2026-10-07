"""Organisation membership and entitlement workflows."""

from django.conf import settings


def organisations_enabled():
    """Return whether organisation subscriptions are enabled for this site."""
    return settings.PEACHJAM.get("ORGANISATION_SUBSCRIPTIONS", False)
