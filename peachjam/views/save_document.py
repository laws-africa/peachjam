import re

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Prefetch, Q
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
from django.views.generic.detail import DetailView

from peachjam.forms import SaveDocumentForm
from peachjam.models import CoreDocument, Folder, SavedDocument, pj_settings
from peachjam.resources import DownloadDocumentsResource

User = get_user_model()


class AllowSavedDocumentMixin:
    def dispatch(self, *args, **kwargs):
        if not pj_settings().allow_save_documents:

            raise Http404("Saving documents is not allowed.")
        return super().dispatch(*args, **kwargs)


class BaseFolderMixin(
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
        context["ungrouped_saved_documents"] = (
            self.request.user.saved_documents.filter(folder__isnull=True)
            .select_related("document")
            .annotate(
                annotation_count=Count(
                    "document__annotations",
                    filter=Q(document__annotations__user=self.request.user),
                )
            )
        )
        context["folders"] = self.request.user.folders.prefetch_related(
            Prefetch(
                "saved_documents",
                queryset=SavedDocument.objects.select_related("document").annotate(
                    annotation_count=Count(
                        "document__annotations",
                        filter=Q(document__annotations__user=self.request.user),
                    )
                ),
            )
        )

        return context


class FolderListView(BaseFolderMixin, ListView):
    permission_required = "peachjam.view_folder"


class BaseFolderFormMixin(BaseFolderMixin):
    success_url = reverse_lazy("folder_list")
    fields = ["name"]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.htmx and self.request.htmx.prompt:
            data = kwargs["data"].copy()
            data["name"] = self.request.htmx.prompt
            kwargs["data"] = data
        return kwargs


class FolderCreateView(BaseFolderFormMixin, CreateView):
    permission_required = "peachjam.add_folder"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        instance = Folder()
        instance.user = self.request.user
        kwargs["instance"] = instance
        return kwargs


class FolderUpdateView(BaseFolderFormMixin, UpdateView):
    permission_required = "peachjam.change_folder"


class FolderDeleteView(BaseFolderMixin, DeleteView):
    success_url = reverse_lazy("folder_list")
    permission_required = "peachjam.delete_folder"


class FolderDownloadView(BaseFolderMixin, DetailView):
    permission_required = "peachjam.download_folder"

    def get(self, request, *args, **kwargs):
        folder = self.get_object()
        pks = [d.pk for d in folder.saved_documents.only("pk")]
        dataset = DownloadDocumentsResource().export(
            DownloadDocumentsResource.get_objects_for_download(pks)
        )
        fmt = DownloadDocumentsResource.download_formats["xlsx"]()
        data = fmt.export_data(dataset)

        response = HttpResponse(data, content_type=fmt.get_content_type())
        fname = re.sub(r"[^a-zA-Z0-9-]", "-", folder.name) + "." + fmt.get_extension()
        response["Content-Disposition"] = f'attachment; filename="{fname}"'
        return response


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
    template_name = "peachjam/saved_document_update.html"
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
    template_name = "peachjam/saved_document_create.html"
    permission_required = "peachjam.add_saveddocument"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        instance = SavedDocument()
        instance.user = self.request.user
        doc_id = self.request.GET.get("doc_id")
        if doc_id:
            try:
                document = get_object_or_404(CoreDocument, pk=int(doc_id))
                instance.document = document
            except ValueError:
                pass
        kwargs["instance"] = instance
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
