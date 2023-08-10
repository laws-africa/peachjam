def obl_microsites(request):
    return {"MICROSITE": getattr(request, "microsite", None)}
