import datetime
import json

from django import template
from django.http import QueryDict
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

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


@register.filter
def parse_isodate_string(date):
    return datetime.datetime.fromisoformat(date)


@register.simple_tag
def get_proper_elided_page_range(paginator, number, on_each_side=3, on_ends=2):
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
def build_taxonomy_url(item, prefix="taxonomy"):
    items = []
    root = item.root if hasattr(item, "root") else item.get_root()
    if root != item:
        items.append(root.slug)
    items.append(item.slug)
    return f"/{prefix}/" + "/".join(items)


@register.simple_tag
def jurisdiction_icon(doc):
    code = doc.expression_frbr_uri.split("/")[2].split("-")[0]
    if code == "aa":
        return mark_safe(
            '<img style="width:1.33333em; vertical-align: baseline" alt="African Union Icon" '
            'src="/static/images/au_icon.png">'
        )
    return mark_safe(f'<span class ="fi fi-{code}"></span>')


@register.filter
def split(value, sep=None):
    return [v.strip() for v in value.split(sep)]


@register.filter
def get_follow_params(obj):
    # this would be better as a model method
    return f"{'_'.join(obj._meta.verbose_name.lower().split())}={obj.pk}"


@register.simple_tag
def json_table(data):
    def make_table(info):
        return mark_safe(
            '<table class="table table-sm">'
            + "".join(make_row(key, value) for key, value in info.items())
            + "</table>"
        )

    def make_row(key, value):
        return format_html(
            '<tr><th style="width: 7em">{}</th><td>', key
        ) + render_value(value)

    def render_value(value):
        if isinstance(value, dict):
            return make_table(value)
        elif isinstance(value, list):
            s = "<ol>"
            s += "".join(["<li>" + render_value(v) + "</li>" for v in value])
            s += "</ol>"
            return s
        else:
            return format_html("{}", value)

    return make_table(data or {})
