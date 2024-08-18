from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
)
from django.views.generic.edit import FormMixin

from peachjam.forms import FolderForm, SaveDocumentForm
from peachjam.models import CoreDocument, Folder, SavedDocument

User = get_user_model()


class BaseFolderView(LoginRequiredMixin, PermissionRequiredMixin):
    model = Folder

    def get_template_names(self):
        if self.request.htmx:
            return ["peachjam/_folders_list.html"]
        return ["peachjam/folders_list.html"]

    def get_queryset(self):
        return self.request.user.folders.all()

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ungrouped_saved_documents"] = self.request.user.saved_documents.filter(
            folder__isnull=True
        )
        context["folders"] = self.get_queryset()
        return context


class FolderListView(BaseFolderView, ListView):
    permission_required = "peachjam.view_folder"


class BaseFolderFormView(BaseFolderView, FormMixin):
    success_url = reverse_lazy("folder_list")
    form_class = FolderForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs


class FolderCreateView(BaseFolderFormView, CreateView):
    permission_required = "peachjam.add_folder"


class FolderUpdateView(BaseFolderFormView, UpdateView):
    permission_required = "peachjam.change_folder"


class FolderDeleteView(BaseFolderFormView, DeleteView):
    permission_required = "peachjam.delete_folder"


class SavedDocumentButtonView(TemplateView):
    template_name = "peachjam/saved_document_login.html"

    def get(self, *args, **kwargs):
        document = CoreDocument.objects.filter(pk=self.kwargs["doc_id"]).first()
        if self.request.user.is_authenticated:
            saved_doc = SavedDocument.objects.filter(
                document=document, user=self.request.user
            ).first()
            if saved_doc:
                return HttpResponseRedirect(
                    reverse("saved_document_update", kwargs={"pk": saved_doc.pk})
                )
            return HttpResponseRedirect(
                reverse("saved_document_create") + f"?doc_id={document.pk}"
            )
        context = self.get_context_data()
        context["document"] = document
        return self.render_to_response(context)


class BaseSavedDocumentFormView(
    FormMixin,
):
    template_name = "peachjam/saved_document.html"
    form_class = SaveDocumentForm
    context_object_name = "saved_document"
    model = SavedDocument

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse(
            "saved_document_update",
            kwargs={
                "pk": self.object.pk,
            },
        )


class SavedDocumentCreateView(
    PermissionRequiredMixin, BaseSavedDocumentFormView, CreateView
):
    permission_required = "peachjam.add_saveddocument"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        doc_id = self.request.GET.get("doc_id")
        if doc_id:
            try:
                doc_id = int(doc_id)
                document = CoreDocument.objects.filter(pk=doc_id).first()
                kwargs.update({"initial": {"document": document}})
            except ValueError:
                pass
        return kwargs


class SavedDocumentUpdateView(
    PermissionRequiredMixin, BaseSavedDocumentFormView, UpdateView
):
    permission_required = "peachjam.change_saveddocument"


class SavedDocumentDeleteView(
    PermissionRequiredMixin, BaseSavedDocumentFormView, DeleteView
):
    permission_required = "peachjam.delete_saveddocument"

    def post(self, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        response = HttpResponse("saved document deleted")
        response["HX-Refresh"] = "true"
        return response
