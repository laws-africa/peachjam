"""The save document views work closely with HTMX to provide a dynamic saving experience without heavy client-side
Javascript. This also means that we can use caching on document listing views while still showing up-to-date
details for saved documents.

When a page loads, it includes elements with data-document-id="123" attributes indicate the documents included on
the page. In listing views, this is included by the document table row template. The document detail page also includes
it. All pages include a placeholder saved-document-modal which is used when the user saves or edits a saved document.

Some custom Javascript finds all the document IDs on the page and uses HTMX to load the various saved document
HTML fragments into the page, including:

* the star for saved documents
* the Save/Unsave button
* the folder and note details included in the document table

If a document is not saved, then the Save button submits a POST to save the document. The response to that request
includes all the HTML fragments for the newly saved document, and the contents of the saved-document-modal which is
shown by the Save button.

If a document is already saved, then clicking on the Save button opens the modal and uses HTMX to load the "update"
form into the modal.

When the Unsave button is clicked, a POST request is sent to delete the saved document. That response redirects to the
bulk fragments URL to re-load all the (now unsaved) fragments for that document.

In summary:

* various page elements are injected (possibly in bulk) via the fragments endpoint using HTMX
* Bootstrap is used to toggle a single, global Saved Document modal
* HTMX is used to inject the correct content into the modal when it is shown
"""
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Prefetch
from django.forms.forms import Form
from django.http import Http404
from django.http.response import HttpResponse, HttpResponseBadRequest
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
from peachjam_subs.models import Subscription

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
        context = super().get_context_data(*args, **kwargs)

        context["folders"] = self.request.user.folders.prefetch_related(
            Prefetch(
                "saved_documents",
                queryset=SavedDocument.objects.for_user_with_related(self.request.user),
            )
        )

        sub = Subscription.objects.active_for_user(self.request.user).first()
        if sub:
            (
                context["folder_limit_reached"],
                context["folder_upgrade"],
            ) = sub.check_feature_limit("folder_limit")

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


class SavedDocumentFragmentsView(AllowSavedDocumentMixin, TemplateView):
    """Renders saved document html fragments for multiple documents. Used from the search results page."""

    template_name = "peachjam/saved_document/_fragments.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            requested_ids = [int(pk) for pk in self.request.GET.getlist("doc_id")]
        except ValueError:
            requested_ids = []

        requested_ids = requested_ids[:50]  # sanity limit

        # Fetch all requested CoreDocuments
        docs = {
            doc.id: doc for doc in CoreDocument.objects.filter(pk__in=requested_ids)
        }

        saved_docs = {}

        if self.request.user.is_authenticated and docs:
            # Get all SavedDocuments for works linked to requested CoreDocuments
            work_ids = [doc.work_id for doc in docs.values()]
            existing_sds = SavedDocument.objects.filter(
                user=self.request.user,
                work_id__in=work_ids,
            ).select_related("work")

            # Map by work_id for lookup
            saved_by_work = {sd.work_id: sd for sd in existing_sds}

            # Match each doc to a SavedDocument (by work)
            for doc_id, doc in docs.items():
                sd = saved_by_work.get(doc.work_id)
                if sd:
                    setattr(sd, "document", doc)
                    saved_docs[doc_id] = (sd, SaveDocumentForm(instance=sd))

        # Create fake SavedDocuments for any missing ones
        for doc_id, doc in docs.items():
            if doc_id not in saved_docs:
                sd = SavedDocument(work=doc.work)
                setattr(sd, "document", doc)
                saved_docs[doc_id] = (
                    sd,
                    None,
                )
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

    def form_invalid(self, form):
        return HttpResponseBadRequest(form.errors)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        sub = Subscription.objects.active_for_user(self.object.user).first()
        if sub:
            (
                context["saved_document_limit_reached"],
                context["saved_document_upgrade"],
            ) = sub.check_feature_limit("saved_document_limit")
            (
                context["folder_limit_reached"],
                context["folder_upgrade"],
            ) = sub.check_feature_limit("folder_limit")
        context["next"] = self.request.GET.get("next") or ""
        context["target"] = self.request.GET.get("target") or ""
        return context

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
    http_method_names = ["post"]

    def dispatch(self, request, *args, **kwargs):
        doc_id = request.GET.get("doc_id")
        if not doc_id or not doc_id.isdigit():
            raise Http404

        self.document = get_object_or_404(CoreDocument, pk=doc_id)
        self.work = self.document.work
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
        self.object = SavedDocument(user=self.request.user, work=self.work)
        return super().get_form_kwargs()

    def form_valid(self, form):
        self.object = form.save()
        # this ensures the form reflects the actual saved document
        form = self.form_class(instance=self.object)
        return self.render_to_response(
            self.get_context_data(saved_document=self.object, form=form)
        )

    def form_invalid(self, form):
        self.object = SavedDocument(user=self.request.user, work=self.work)
        return self.render_to_response(
            self.get_context_data(saved_document=self.object, form=form)
        )


class SavedDocumentUpdateView(SavedDocumentFormMixin, UpdateView):
    template_name = "peachjam/saved_document/_update.html"
    permission_required = "peachjam.change_saveddocument"
    http_method_names = ["post"]

    def get_object(self, queryset=None):
        sd = super().get_object(queryset)
        doc_id = self.request.GET.get("doc_id")
        if doc_id and doc_id.isdigit():
            document = sd.work.documents.filter(id=doc_id).first()
            setattr(sd, "document", document)
        return sd


class SavedDocumentModalView(SavedDocumentUpdateView):
    template_name = "peachjam/saved_document/_update_modal.html"
    http_method_names = ["get"]


class SavedDocumentDeleteView(SavedDocumentFormMixin, DeleteView):
    permission_required = "peachjam.delete_saveddocument"
    # stub form that always validates
    form_class = Form
    http_method_names = ["post"]
