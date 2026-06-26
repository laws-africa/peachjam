from urllib.parse import urlencode

from django import template
from django.urls.base import reverse

register = template.Library()


UPSELL_URL_NAME = "check_subscription"
CHANGE_SUBSCRIPTION_URL_NAME = "subscribe"


@register.simple_tag
def upsell_url(product, next_url=None):
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
    return url + f"?{urlencode(extra)}"


@register.simple_tag(takes_context=True)
def change_subscription_url(context, next_url=None):
    """Generate a URL for changing a user's subscription, with a next URL back to the current page."""
    request = context.get("request")
    if not next_url and request:
        next_url = getattr(getattr(request, "htmx", None), "current_url_abs_path", None)
        if not next_url:
            next_url = request.get_full_path()

    url = reverse(CHANGE_SUBSCRIPTION_URL_NAME)
    if next_url:
        return url + f"?{urlencode({'next': next_url})}"
    return url


@register.simple_tag
def login_url_with_next(next_url):
    """Generate a login URL that redirects back to the given URL after login."""
    return f"{reverse('account_login')}?" + urlencode({"next": next_url})
