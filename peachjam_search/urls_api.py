from django.urls import path

from . import views

urlpatterns = [
    # public-facing API
    path("portions", views.PortionSearchView.as_view(), name="api_portion_search"),
]
