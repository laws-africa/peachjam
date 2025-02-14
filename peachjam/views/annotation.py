from django.views.generic import ListView

from peachjam.models import Annotation


class AnnotationListView(ListView):
    template_name = "peachjam/annotation_list.html"
    context_object_name = "annotations"

    def get_queryset(self):
        return Annotation.objects.filter(user=self.request.user)
