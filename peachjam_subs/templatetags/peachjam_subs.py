from django import template
from django.urls.base import reverse

register = template.Library()


UPSELL_URL_NAME = "subscribe"


@register.simple_tag
def upsell_url(product):
    return reverse(UPSELL_URL_NAME)
