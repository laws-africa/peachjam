from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.shortcuts import get_object_or_404, render


def comment_form_view(request, app_label, model_name, pk):
    """Renders a list of comments for the admin view, refreshed using htmx after posting a comment."""
    if not request.user.is_authenticated or not request.user.is_staff:
        raise Http404()

    content_type = get_object_or_404(ContentType, app_label=app_label, model=model_name)
    obj = get_object_or_404(content_type.model_class(), pk=pk)
    return render(
        request,
        "admin/_comments_form_combo.html",
        {
            "object": obj,
            "model_name": model_name,
            "app_label": app_label,
        },
    )
