from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.urls import reverse
from django.utils.functional import cached_property
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
)
from django.views.generic.edit import ModelFormMixin

from peachjam.forms import SaveDocumentForm
from peachjam.models import CoreDocument, Folder, SavedDocument

User = get_user_model()


class BaseSavedDocumentView(PermissionRequiredMixin):
    model = Folder

    def get_template_names(self):
        if self.request.htmx:
            return ["peachjam/_folders_list.html"]
        return ["peachjam/saved_document_list.html"]

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ungrouped_saved_documents"] = self.request.user.saved_documents.filter(
            folder__isnull=True
        )
        context["folders"] = self.request.user.folders.all()
        return context


class SavedDocumentListView(BaseSavedDocumentView, ListView):
    permission_required = "peachjam.view_folder"


class CreateFolderView(BaseSavedDocumentView, CreateView):
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


class UpdateFolderView(BaseSavedDocumentView, UpdateView):
    permission_required = "peachjam.update_folder"
    fields = ["name"]

    def post(self, request: HttpRequest, *args, **kwargs):
        if request.htmx:
            new_folder_name = request.htmx.prompt
            self.object = self.get_object()
            self.object.name = new_folder_name
            self.object.save()
        return self.render_to_response(self.get_context_data(*args, **kwargs))


class DeleteFolderView(BaseSavedDocumentView, DeleteView):
    permission_required = "peachjam.delete_folder"
    model = Folder

    def post(self, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        response = HttpResponse("saved document deleted")
        response["HX-Refresh"] = "true"
        return response


class BaseSaveDocumentView:
    template_name = "peachjam/save_document.html"

    @cached_property
    def document(self):
        return CoreDocument.objects.filter(pk=self.kwargs["doc_id"]).first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["document"] = self.document
        return context


class SaveDocumentFormView(
    BaseSaveDocumentView, ModelFormMixin, PermissionRequiredMixin
):
    form_class = SaveDocumentForm
    context_object_name = "saved_document"
    model = SavedDocument

    def get_form_kwargs(self, *args, **kwargs):
        kwargs = super().get_form_kwargs()
        kwargs.update({"user": self.request.user, "document": self.document})
        return kwargs

    def get_success_url(self):
        return reverse(
            "saved_document_update",
            kwargs={
                "doc_id": self.document.pk,
                "pk": self.object.pk,
            },
        )


class SaveDocumentAuthView(BaseSaveDocumentView, TemplateView):
    template_name = "peachjam/save_document.html"


class SaveDocumentView(SaveDocumentFormView, CreateView):
    permission_required = "peachjam.add_saveddocument"


class UpdateSavedDocumentView(SaveDocumentFormView, UpdateView):
    permission_required = "peachjam.update_saveddocument"


class UnSaveDocumentView(SaveDocumentFormView, DeleteView):
    permission_required = "peachjam.delete_saveddocument"

    def get_success_url(self):
        return reverse("save_document", kwargs={"doc_id": self.document.pk})

    def post(self, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        response = HttpResponse("saved document deleted")
        response["HX-Refresh"] = "true"
        return response
