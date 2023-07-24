from django.contrib.staticfiles import finders

searched_locations = finders.searched_locations


def obl_microsites(request):
    if not hasattr(request, "microsite"):
        return {}
    return {"MICROSITE": request.microsite}
