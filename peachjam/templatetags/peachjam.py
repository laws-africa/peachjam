import datetime
import json

from django import template
from django.core.paginator import Paginator
from django.urls import reverse

register = template.Library()


@register.filter
def jsonify(value):
    return json.dumps(value)


@register.filter
def admin_url(obj, verb):
    return reverse(
        "admin:%s_%s_%s" % (obj._meta.app_label, obj._meta.model_name, verb),
        args=[obj.pk],
    )


@register.filter
def strip_first_character(value):
    return value[1:]


@register.filter
def parse_string_date(date):
    return datetime.datetime.strptime(date, "%Y-%m-%d")


@register.simple_tag
def get_proper_elided_page_range(p, number, on_each_side=3, on_ends=2):
    paginator = Paginator(p.object_list, p.per_page)
    return paginator.get_elided_page_range(
        number=number, on_each_side=on_each_side, on_ends=on_ends
    )
