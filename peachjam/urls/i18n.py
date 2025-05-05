from django.urls import include, path

from peachjam.views.language import set_preferred_language

urlpatterns = [
    path("", include("django.conf.urls.i18n")),
    path(
        "set_preferred_language/", set_preferred_language, name="set_preferred_language"
    ),
]
