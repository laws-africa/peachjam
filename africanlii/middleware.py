from django.shortcuts import redirect


class RedirectAGPMiddleware:
    """Redirect agp to non-agp permanently."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        host = request.get_host()
        if host and host == "agp.africanlii.org":
            return redirect(
                f"https://africanlii.org{request.get_full_path()}", permanent=True
            )

        return response
