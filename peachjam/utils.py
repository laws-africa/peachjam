import string
from functools import wraps

from django.utils.translation import get_language_from_request
from languages_plus.models import Language


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


def get_language(request):
    language = get_language_from_request(request)
    return Language.objects.get(iso_639_1__iexact=language).iso_639_3
