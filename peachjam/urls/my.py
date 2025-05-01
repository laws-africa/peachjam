from django.urls import path

from peachjam.views import MyHomeView

urlpatterns = [
    path("", MyHomeView.as_view(), name="my_home"),
]
