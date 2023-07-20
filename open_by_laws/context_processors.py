from peachjam.models import Locality


def open_by_laws(request):
    """
    Add some useful context to templates.
    """
    return {
        "LOCALITIES": Locality.objects.all(),
    }
