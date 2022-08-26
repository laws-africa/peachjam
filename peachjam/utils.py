import datetime
import string
from functools import wraps


def lowercase_alphabet():
    return " ".join(string.ascii_lowercase).split()


def add_slash(frbr_uri):
    # adds the leading slash if not present
    if frbr_uri[0] != "/":
        return f"/{frbr_uri}"
    return frbr_uri


def add_slash_to_frbr_uri(*args, **kwargs):
    def decorator(view_func, *args, **kwargs):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            kwargs["frbr_uri"] = add_slash(kwargs.get("frbr_uri"))
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def convert_string_date_to_datetime(date):
    return datetime.datetime.strptime(date, "%Y-%m-%d")
