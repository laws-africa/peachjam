import datetime
import json
import os

from django import template
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.paginator import Paginator
from django.http import QueryDict
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


@register.simple_tag
def query_string(*args, **kwargs):
    """
    Combines dictionaries of query parameters and individual query parameters
    and builds an encoded URL query string from the result.
    """
    query_dict = QueryDict(mutable=True)

    for a in args:
        query_dict.update(a)

    remove_keys = []

    for k, v in kwargs.items():
        if v is None:
            remove_keys.append(k)
        elif isinstance(v, list):
            query_dict.setlist(k, v)
        else:
            query_dict[k] = v

    for k in remove_keys:
        if k in query_dict:
            del query_dict[k]

    qs = query_dict.urlencode()
    return f"{qs}" if qs else ""


@register.simple_tag
def user_name(user):
    if user.first_name:
        name = user.first_name
        if user.last_name:
            name = user.first_name + " " + user.last_name
    else:
        name = user.username

    return name


@register.simple_tag
def build_taxonomy_url(item):
    items = [item.slug]
    item = item.get_parent()
    while item:
        items.insert(0, item.slug)
        item = item.get_parent()

    return "/taxonomy/" + "/".join(items)


@register.filter(name="file_exists")
def file_exists(path):
    p = staticfiles_storage.path(path)
    print(p)
    if os.path.isfile(p):
        print(True)
    return path
