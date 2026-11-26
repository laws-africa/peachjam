"""Extension point for account links without changing their return destinations."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from allauth.account.adapter import get_adapter


def account_url(request, url, *, action=None, permission=None, next_url=None):
    """Build an account link and let the configured adapter customise it."""
    if next_url is not None:
        parts = urlsplit(url)
        query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key != "next"
        ]
        query.append(("next", next_url))
        url = urlunsplit(parts._replace(query=urlencode(query)))
    hook = getattr(get_adapter(request), "get_account_url", None)
    return hook(request, url, action=action, permission=permission) if hook else url
