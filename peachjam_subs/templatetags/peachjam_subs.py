from urllib.parse import urlencode

from django import template
from django.urls.base import reverse

from peachjam.account_urls import account_url
from peachjam_subs.limits import get_subscription_locked_data_summary

register = template.Library()


UPSELL_URL_NAME = "check_subscription"
CHANGE_SUBSCRIPTION_URL_NAME = "subscribe"


@register.simple_tag(takes_context=True)
def upsell_url(context, product, next_url=None, permission=None, action="subscribe"):
    """Generate a URL that takes the user to the subscription upsell page for the given product, with an optional
    next URL to redirect back to after subscribing. Generally, the upsell view will check if the user is already
    subscribed, and if so, just redirect to the next URL. If not, it will give the user the chance to change
    their subscription.
    """
    url = reverse(UPSELL_URL_NAME)
    extra = {
        "product": product.name,
    }
    if next_url:
        extra["next"] = next_url

    return account_url(
        context.get("request"),
        url + f"?{urlencode(extra)}",
        action=action,
        permission=permission or context.get("required_permission"),
    )


@register.simple_tag(takes_context=True)
def change_subscription_url(context, next_url=None, permission=None):
    """Generate a URL for changing a user's subscription, with a next URL back to the current page."""
    request = context.get("request")
    if not next_url and request:
        next_url = getattr(getattr(request, "htmx", None), "current_url_abs_path", None)
        if not next_url:
            next_url = request.get_full_path()

    url = reverse(CHANGE_SUBSCRIPTION_URL_NAME)
    if next_url:
        url += f"?{urlencode({'next': next_url})}"

    return account_url(request, url, action="upgrade", permission=permission)


@register.simple_tag
def subscription_locked_data_summary(user):
    """Return a compact summary of subscription-locked data for a user."""
    if not user.is_authenticated:
        return None
    return get_subscription_locked_data_summary(user)


@register.simple_tag(takes_context=True)
def login_url_with_next(context, next_url):
    """Build a login link with a return destination and optional account customisation."""

    return account_url(
        context.get("request"),
        reverse("account_login"),
        action="login",
        permission=context.get("required_permission"),
        next_url=next_url,
    )
