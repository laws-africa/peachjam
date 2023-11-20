import os
import string
import subprocess
import tempfile
from datetime import datetime
from functools import wraps

import martor.utils
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
    """Get language from the request object and return its 3-letter language code."""
    if not hasattr(request, "language"):
        language = get_language_from_request(request)
        # store it on the request object because it won't change
        request.language = Language.objects.get(iso_639_1__iexact=language).iso_639_3
    return request.language


def pdfjs_to_text(fname):
    """Extract text from fname using pdfjs-compatible script."""
    with tempfile.NamedTemporaryFile(suffix=".txt") as outf:
        cmd = [
            os.path.join(os.path.dirname(__file__), "..", "bin", "pdfjs-to-text"),
            fname,
            outf.name,
        ]

        subprocess.run(cmd, check=True)
        return outf.read().decode("utf-8")


def chunks(lst, n):
    """Yield successive n-sized chunks from list."""
    for i in range(n):
        yield lst[i::n]


class ISODateConverter:
    regex = r"\d{4}-\d{2}-\d{2}"

    def to_python(self, value):
        # invalid values will raise ValueError which will raise 404
        return datetime.strptime(value, "%Y-%m-%d").date()

    def to_url(self, value):
        # invalid values will raise ValueError which will raise NoReverseMatch
        return datetime.strptime(value, "%Y-%m-%d").date().strftime("%Y-%m-%d")


def parse_utf8_html(html):
    """Parse html assuming utf8 encoding and return lxml tree."""
    import lxml.html

    parser = lxml.html.HTMLParser(encoding="utf-8")
    return lxml.html.fromstring(html, parser=parser)


def markdownify(text):
    """Convert markdown text to html using pandoc on the commandline."""
    with tempfile.NamedTemporaryFile(suffix=".md") as inf:
        with tempfile.NamedTemporaryFile(suffix=".html") as outf:
            inf.write(text.encode("utf-8"))
            inf.flush()
            cmd = [
                "pandoc",
                "--from=markdown",
                "--to=html",
                "--output",
                outf.name,
                inf.name,
            ]
            subprocess.run(cmd, check=True)
            return outf.read().decode("utf-8")


# override martor's markownify to use pandoc, so that we get alpha-numbered list support
martor.utils.markdownify = markdownify
