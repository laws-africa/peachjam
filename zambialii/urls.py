from django.urls import include, path

from zambialii import views

urlpatterns = [
    path("paralegals/", views.ParalegalsView.as_view(), name="paralegals"),
    path("", include("liiweb.urls")),
]
