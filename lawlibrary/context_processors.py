from lawlibrary.constants import MUNICIPAL_CODES, PROVINCIAL_CODES


def lawlibrary(request):
    """
    Add some useful context to templates.
    """
    return {
        "PROVINCIAL_CODES": PROVINCIAL_CODES,
        "MUNICIPAL_CODES": MUNICIPAL_CODES,
    }
