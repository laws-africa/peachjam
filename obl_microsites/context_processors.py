def obl_microsites(request):
    if not hasattr(request, "microsite"):
        return {}
    return {"MICROSITE": request.microsite}
