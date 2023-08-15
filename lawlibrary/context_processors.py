from lawlibrary.constants import PROVINCIAL_CODES


def lawlibrary(request):
    """
    Add some useful context to templates.
    """
    return {
        "PROVINCIAL_CODES": PROVINCIAL_CODES,
    }
