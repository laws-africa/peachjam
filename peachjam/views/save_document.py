import re

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Prefetch, Q
from django.forms.forms import Form
from django.http import Http404
from django.http.response import HttpResponse
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
            return ["peachjam/saved_document/_folders_list.html"]
        return ["peachjam/saved_document/folders_list.html"]

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
                queryset=SavedDocument.objects.select_related("document")
                .prefetch_related("document__labels")
                .annotate(
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
    tab = "saved_documents"


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
        pks = [sd.document_id for sd in folder.saved_documents.only("document_id")]
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
    """Renders saved document buttons and other details for use in a document detail page."""

    def get_template_names(self):
        if self.saved_document:
            return ["peachjam/saved_document/_update.html"]
        return ["peachjam/saved_document/_create.html"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["document"] = document = get_object_or_404(
            CoreDocument, pk=self.kwargs["doc_id"]
        )

        if self.request.user.is_authenticated:
            context[
                "saved_document"
            ] = self.saved_document = self.request.user.saved_documents.filter(
                document=document
            ).first()
            if self.saved_document:
                context["form"] = SaveDocumentForm(instance=self.saved_document)
        else:
            # redirect URL for the next button for non-authenticated users
            context["next_url"] = self.request.headers.get("HX-Current-URL")

        return context


class SavedDocumentFragmentsView(AllowSavedDocumentMixin, TemplateView):
    """Renders saved document html fragments for multiple documents. Used from the search results page."""

    template_name = "peachjam/saved_document/_bulk.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        pks = []
        try:
            pks = [int(pk) for pk in self.request.GET.getlist("doc_id")]
        except ValueError:
            pass
        # validate the pks - first few only
        docs = {doc.id: doc for doc in CoreDocument.objects.filter(pk__in=pks)[:20]}
        saved_docs = {}

        if self.request.user.is_authenticated:
            # stash saved documents and forms (for updating) for ones that are already saved
            saved_docs = {
                sd.document_id: (
                    sd,
                    SaveDocumentForm(instance=sd),
                )
                for sd in SavedDocument.objects.filter(
                    user=self.request.user, document_id__in=docs.keys()
                )
                .select_related("document", "folder")
                .all()
            }

        # fake saved docs for the ones that don't exist
        for doc in docs.values():
            if doc.id not in saved_docs:
                saved_docs[doc.id] = (SavedDocument(document=doc), None)

        context["saved_documents"] = saved_docs.values()
        return context


class SavedDocumentFormMixin(
    AllowSavedDocumentMixin, LoginRequiredMixin, PermissionRequiredMixin
):
    form_class = SaveDocumentForm
    context_object_name = "saved_document"
    model = SavedDocument

    def get_queryset(self):
        return self.request.user.saved_documents.all()

    def form_valid(self, form):
        return super().form_valid(form)

    def get_success_url(self):
        # by default, we always redirect to the bulk view which refreshes this document's saved doc details in the page
        return (
            self.request.GET.get("next")
            or reverse(
                "saved_document_fragments",
            )
            + f"?doc_id={self.object.document.id}"
        )


class SavedDocumentCreateView(SavedDocumentFormMixin, CreateView):
    """Creates a saved document and renders the updated details to the page, as well as into the modal which will have
    been opened by the save action."""

    template_name = "peachjam/saved_document/_created.html"
    permission_required = "peachjam.add_saveddocument"

    def dispatch(self, request, *args, **kwargs):
        doc_id = self.request.GET.get("doc_id")
        if doc_id:
            try:
                document = get_object_or_404(CoreDocument, pk=int(doc_id))
                self.document = document
            except ValueError:
                pass
        else:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            # user is not logged in
            self.template_name = "peachjam/saved_document/_anon_modal.html"
            return self.render_to_response(
                {
                    "document": self.document,
                    "next_url": self.request.htmx.current_url,
                }
            )
        return super().handle_no_permission()

    def get_form_kwargs(self):
        self.object = SavedDocument(user=self.request.user, document=self.document)
        return super().get_form_kwargs()

    def form_valid(self, form):
        """If the form is valid, save the associated model."""
        self.object = form.save()
        return self.render_to_response(
            self.get_context_data(saved_document=self.object, form=form)
        )


class SavedDocumentUpdateView(SavedDocumentFormMixin, UpdateView):
    template_name = "peachjam/saved_document/_update.html"
    permission_required = "peachjam.change_saveddocument"


class SavedDocumentModalView(SavedDocumentUpdateView):
    template_name = "peachjam/saved_document/_update_modal.html"


class SavedDocumentDeleteView(SavedDocumentFormMixin, DeleteView):
    permission_required = "peachjam.delete_saveddocument"
    # stub form that always validates
    form_class = Form
