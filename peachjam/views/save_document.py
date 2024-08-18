from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.urls import reverse, reverse_lazy
from django.utils.functional import cached_property
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
)
from django.views.generic.edit import FormMixin

from peachjam.forms import SaveDocumentForm
from peachjam.models import CoreDocument, Folder, SavedDocument

User = get_user_model()


class BaseFolderView(PermissionRequiredMixin):
    model = Folder

    def get_template_names(self):
        if self.request.htmx:
            return ["peachjam/_folders_list.html"]
        return ["peachjam/folders_list.html"]

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ungrouped_saved_documents"] = self.request.user.saved_documents.filter(
            folder__isnull=True
        )
        context["folders"] = self.request.user.folders.all()
        return context


class FolderListView(BaseFolderView, ListView):
    permission_required = "peachjam.view_folder"


class FolderCreateView(BaseFolderView, CreateView):
    permission_required = "peachjam.add_folder"
    fields = ["name"]

    def post(self, request: HttpRequest, *args, **kwargs):
        if request.htmx:
            folder_name = request.htmx.prompt
            self.object = Folder.objects.create(
                user=self.request.user, name=folder_name
            )
        context = self.get_context_data(*args, **kwargs)
        return self.render_to_response(context)


class FolderUpdateView(BaseFolderView, UpdateView):
    permission_required = "peachjam.change_folder"
    fields = ["name"]

    def post(self, request: HttpRequest, *args, **kwargs):
        if request.htmx:
            new_folder_name = request.htmx.prompt
            self.object = self.get_object()
            self.object.name = new_folder_name
            self.object.save()
        return self.render_to_response(self.get_context_data(*args, **kwargs))


class FolderDeleteView(BaseFolderView, DeleteView):
    permission_required = "peachjam.delete_folder"
    model = Folder

    def post(self, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        response = HttpResponse("folder deleted")
        response["HX-Refresh"] = "true"
        return response


class SaveDocumentFormView(
    FormMixin,
):
    template_name = "peachjam/save_document.html"
    form_class = SaveDocumentForm
    context_object_name = "saved_document"
    model = SavedDocument

    def get_form_kwargs(self, *args, **kwargs):
        kwargs = super().get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def get_success_url(self):
        return reverse(
            "saved_document_update",
            kwargs={
                "pk": self.object.pk,
            },
        )


class SavedDocumentButtonView(SaveDocumentFormView, TemplateView):
    @cached_property
    def document(self):
        return CoreDocument.objects.filter(pk=self.kwargs["doc_id"]).first()

    def get_form_kwargs(self, *args, **kwargs):
        kwargs = super().get_form_kwargs()
        kwargs.update({"initial": {"document": self.document}})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["document"] = self.document
        if self.request.user.is_authenticated:
            context["saved_document"] = SavedDocument.objects.filter(
                document=self.document, user=self.request.user
            ).first()
        return context


class SavedDocumentCreateView(
    PermissionRequiredMixin, SaveDocumentFormView, CreateView
):
    permission_required = "peachjam.add_saveddocument"


class SavedDocumentUpdateView(
    PermissionRequiredMixin, SaveDocumentFormView, UpdateView
):
    permission_required = "peachjam.change_saveddocument"


class SavedDocumentDeleteView(
    PermissionRequiredMixin, SaveDocumentFormView, DeleteView
):
    permission_required = "peachjam.delete_saveddocument"
    success_url = reverse_lazy("saved_document_create")

    def post(self, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        response = HttpResponse("saved document deleted")
        response["HX-Refresh"] = "true"
        return response
