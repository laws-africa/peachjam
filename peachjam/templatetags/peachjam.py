import datetime
import hashlib
import json
from urllib.parse import urljoin

from django import template
from django.db.models import F, Window
from django.db.models.functions import RowNumber
from django.http import QueryDict
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from peachjam.auth import user_display
from peachjam.models import DocumentChatThread
from peachjam.xmlutils import qualify_local_refs as qualify_local_refs_html

register = template.Library()


def normalize_base_url(value, protocol="https"):
    value = str(value or "").strip()
    if not value:
        return ""

    if "://" not in value:
        value = f"{protocol}://{value.lstrip('/')}"

    return value.rstrip("/") + "/"


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
    root_slug = getattr(item, "root_slug", None)
    if root_slug is None:
        root = getattr(item, "root", None)
        if root is not None:
            root_slug = root.slug
        elif hasattr(item, "is_root") and item.is_root():
            root_slug = item.slug
        else:
            root_slug = item.get_root().slug
    if root_slug != item.slug:
        items.append(root_slug)
    items.append(item.slug)
    return f"/{prefix}/" + "/".join(items)


@register.simple_tag
def absolute_url(site_or_domain, path="", protocol="https"):
    domain = getattr(site_or_domain, "domain", site_or_domain)
    base_url = normalize_base_url(domain, protocol)
    if not base_url:
        return ""

    path = "" if path is None else str(path)
    return urljoin(base_url, path.lstrip("/"))


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
def qualify_local_refs(value, frbr_uri):
    return qualify_local_refs_html(value, frbr_uri)


@register.filter
def get_follow_params(obj):
    # this would be better as a model method
    field_map = {
        "courtclass": "court_class",
        "courtregistry": "court_registry",
        "lawreport": "law_report",
    }
    field_name = field_map.get(obj._meta.model_name, obj._meta.model_name)
    return f"{field_name}={obj.pk}"


@register.simple_tag
def json_table(data):
    def make_table(info):
        return mark_safe(
            '<table class="table table-sm">'
            + "".join(make_row(key, value) for key, value in info.items())
            + "</table>"
        )

    def make_row(key, value):
        return (
            format_html('<tr><th style="width: 7em">{}</th><td>', key)
            + render_value(value)
            + "</td></tr>"
        )

    def render_value(value):
        if isinstance(value, dict):
            return make_table(value)
        elif isinstance(value, list):
            s = "<ol>"
            s += "".join(
                [
                    "<li><details><summary>(details)</summary>"
                    + render_value(v)
                    + "</details></li>"
                    for v in value
                ]
            )
            s += "</ol>"
            return s
        else:
            return format_html("{}", value)

    return make_table(data or {})


@register.filter
def get_dotted_key_value(obj, key):
    return obj.get(key, "")


@register.simple_tag
def user_avatar(user, size=40):
    """
    Renders a user's avatar. Uses their social image if available,
    otherwise falls back to a circle with their first initial.
    """

    # Try to get social image (customize this depending on your user model)
    avatar_url = (
        user.userprofile.avatar_url()
    )  # or "https://lh3.googleusercontent.com/a/ACg8ocLLVn6MqHHeblDXalODEv4YFmQBQO6gBtAIqb9RIrJ9pYwX7w=s96-c"
    if avatar_url:
        return format_html(
            '<img src="{}" alt="{}" class="user-avatar" style="width:{}px;height:{}px">',
            avatar_url,
            user.get_full_name() or user.username,
            size,
            size,
        )

    # Fallback to initial avatar
    initial = user_display(user)[:1].upper()

    # Use deterministic background color based on username hash
    color = color_for_user(user)

    return format_html(
        '<div class="user-avatar-letter" '
        'style="width:{}px;height:{}px;background-color:{};font-size:{}px;">{}</div>',
        size,
        size,
        color,
        int(size / 2),
        initial,
    )


def color_for_user(user):
    """Generate a consistent color for each user."""
    h = hashlib.md5(user.username.encode("utf-8")).hexdigest()
    hue = int(h[:2], 16) % 360
    return f"hsl({hue}, 60%, 50%)"


@register.simple_tag
def recent_chats(user):
    """Return the 10 most recent chat threads, one per document, for the supplied user."""
    if not user or not getattr(user, "is_authenticated", False):
        return DocumentChatThread.objects.none()

    return (
        DocumentChatThread.objects.filter(user=user)
        .annotate(
            document_rank=Window(
                expression=RowNumber(),
                partition_by=[F("core_document_id")],
                order_by=F("updated_at").desc(),
            )
        )
        .filter(document_rank=1)
        .select_related("core_document")
        .order_by("-updated_at")[:10]
    )
