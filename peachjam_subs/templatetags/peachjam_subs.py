from urllib.parse import urlencode

from django import template
from django.urls.base import reverse

register = template.Library()


UPSELL_URL_NAME = "check_subscription"


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


@register.simple_tag
def login_url_with_next(next_url):
    """Generate a login URL that redirects back to the given URL after login."""
    return f"{reverse('account_login')}?" + urlencode({"next": next_url})
