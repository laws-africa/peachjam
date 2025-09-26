from django.urls import reverse
from django.views.generic import DeleteView, DetailView, ListView, UpdateView

from peachjam.forms import AnnotationForm
from peachjam.models import Annotation
from peachjam_subs.mixins import SubscriptionRequiredMixin


class BaseAnnotationView(SubscriptionRequiredMixin):
    model = Annotation

    def get_queryset(self):
        return Annotation.objects.filter(
            document=self.kwargs["document_pk"], user=self.request.user
        )


class AnnotationListView(BaseAnnotationView, ListView):
    permission_required = "peachjam.view_annotation"
    template_name = "peachjam/_annotation_list.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context["document_pk"] = self.kwargs["document_pk"]
        return context


class AnnotationDetailView(BaseAnnotationView, DetailView):
    permission_required = "peachjam.view_annotation"
    template_name = "peachjam/_annotation_detail.html"


class AnnotationEditView(BaseAnnotationView, UpdateView):
    permission_required = "peachjam.change_annotation"
    template_name = "peachjam/_annotation_edit.html"
    form_class = AnnotationForm

    def get_success_url(self):
        return reverse(
            "annotation_detail", args=[self.object.document_id, self.object.pk]
        )


class AnnotationDeleteView(BaseAnnotationView, DeleteView):
    permission_required = "peachjam.delete_annotation"
    template_name = "peachjam/_annotation_detail.html"

    def get(self, *args, **kwargs):
        return self.post(*args, **kwargs)

    def get_success_url(self):
        return reverse("annotation_list", args=[self.object.document_id])
