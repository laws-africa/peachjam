import os

from django.conf import settings
from django.http.response import FileResponse


def service_worker(request):
    filepath = os.path.join(
        settings.BASE_DIR, "peachjam/static/js/offline-service-worker.js"
    )
    response = FileResponse(open(filepath, "rb"), content_type="application/javascript")
    # TODO
    response["Cache-Control"] = "no-cache"
    return response
