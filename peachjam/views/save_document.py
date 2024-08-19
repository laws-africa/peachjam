from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
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
from peachjam.models import CoreDocument, Folder, SavedDocument, pj_settings

User = get_user_model()


class AllowSavedDocumentMixin:
    def dispatch(self, *args, **kwargs):
        if not pj_settings().allow_save_documents:

            raise Http404("Saving documents is not allowed.")
        return super().dispatch(*args, **kwargs)


class BaseFolderView(
    AllowSavedDocumentMixin, LoginRequiredMixin, PermissionRequiredMixin
):
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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        instance = Folder()
        instance.user = self.request.user
        kwargs["instance"] = instance
        return kwargs


class FolderUpdateView(BaseFolderFormView, UpdateView):
    permission_required = "peachjam.change_folder"


class FolderDeleteView(BaseFolderFormView, DeleteView):
    permission_required = "peachjam.delete_folder"


class SavedDocumentButtonView(AllowSavedDocumentMixin, TemplateView):
    template_name = "peachjam/saved_document_login.html"

    def get(self, *args, **kwargs):
        document = get_object_or_404(CoreDocument, pk=self.kwargs["doc_id"])
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


class BaseSavedDocumentFormView(AllowSavedDocumentMixin, LoginRequiredMixin):
    template_name = "peachjam/saved_document.html"
    form_class = SaveDocumentForm
    context_object_name = "saved_document"
    model = SavedDocument

    def get_queryset(self):
        return self.request.user.saved_documents.all()

    def get_success_url(self):
        return reverse(
            "saved_document_update",
            kwargs={
                "pk": self.object.pk,
            },
        )


class SavedDocumentCreateView(BaseSavedDocumentFormView, CreateView):
    permission_required = "peachjam.add_saveddocument"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        instance = SavedDocument()
        instance.user = self.request.user
        kwargs["instance"] = instance
        doc_id = self.request.GET.get("doc_id")
        if doc_id:
            try:
                document = get_object_or_404(CoreDocument, pk=int(doc_id))
                kwargs.update({"initial": {"document": document}})
            except ValueError:
                pass
        return kwargs


class SavedDocumentUpdateView(BaseSavedDocumentFormView, UpdateView):
    permission_required = "peachjam.change_saveddocument"


class SavedDocumentDeleteView(BaseSavedDocumentFormView, DeleteView):
    permission_required = "peachjam.delete_saveddocument"

    def post(self, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        response = HttpResponse("saved document deleted")
        response["HX-Refresh"] = "true"
        return response
