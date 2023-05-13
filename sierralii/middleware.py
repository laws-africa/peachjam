from django.shortcuts import redirect


class RedirectToGovSlMiddleware:
    """Redirect to sierralii.gov.sl"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        host = request.get_host()
        if host == "sierralii.org":
            return redirect(
                f"https://sierralii.gov.sl{request.get_full_path()}", permanent=True
            )

        return response
