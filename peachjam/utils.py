import os
import string
import subprocess
import tempfile
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
