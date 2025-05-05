from django.urls import include, path

from peachjam.views.comments import comment_form_view

urlpatterns = [
    path("", include("django_comments.urls")),
    path(
        "form/<str:app_label>/<str:model_name>/<slug:pk>",
        comment_form_view,
        name="comment_form",
    ),
]
