from django.shortcuts import redirect


class RedirectWWWMiddleware:
    """Redirect www to non-www permanently."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        host = request.get_host()
        if host and host.startswith("www."):
            non_www = host[4:]
            return redirect(
                f"https://{non_www}{request.get_full_path()}", permanent=True
            )

        return response
