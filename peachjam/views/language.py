from django.db import transaction
from django.views.i18n import set_language
from languages_plus.models import Language


def set_preferred_language(request):
    response = set_language(request)
    if request.method == "POST" and request.user.is_authenticated:
        language = request.POST.get("language")
        with transaction.atomic():
            request.user.userprofile.preferred_language = Language.objects.get(
                iso_639_1=language
            )
            request.user.userprofile.save()
    return response
