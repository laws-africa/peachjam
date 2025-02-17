from django import forms
from django.db.models import Q
from django.urls import reverse
from django.views.generic import DeleteView, DetailView, ListView, UpdateView

from peachjam.models import Annotation


class BaseAnnotationView:
    model = Annotation
    context_object_name = "annotation"

    def get_queryset(self):
        return Annotation.objects.filter(user=self.request.user)

    def get_object(self, *args, **kwargs):
        return self.get_queryset().get(pk=self.kwargs["pk"])

    def get_success_url(self):
        return reverse("annotation_detail", args=[self.object.pk])


class AnnotationListView(ListView):
    template_name = "peachjam/annotation_list.html"
    context_object_name = "annotations"

    def get_template_names(self):
        if self.request.htmx:
            return ["peachjam/_annotation_list.html"]
        return ["peachjam/annotation_list.html"]

    def get_queryset(self):
        q = self.request.GET.get("q")
        qs = Annotation.objects.filter(user=self.request.user)
        if q:
            q = Q(text__icontains=q) | Q(document__title__icontains=q)
            return qs.filter(q)
        return qs


class AnnotationForm(forms.ModelForm):
    class Meta:
        model = Annotation
        fields = ["text"]


class AnnotationDetailView(BaseAnnotationView, DetailView):
    template_name = "peachjam/annotation_detail.html"


class AnnotationEditView(BaseAnnotationView, UpdateView):
    template_name = "peachjam/annotation_edit.html"
    form_class = AnnotationForm

    def get_success_url(self):
        return reverse("annotation_detail", args=[self.object.pk])


class AnnotationDeleteView(BaseAnnotationView, DeleteView):
    template_name = "peachjam/annotation_detail.html"
    context_object_name = "annotation"

    def get(self, *args, **kwargs):
        return self.post(*args, **kwargs)

    def get_success_url(self):
        return reverse("annotation_list")
