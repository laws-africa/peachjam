from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import HttpRequest
from django.views.generic import DeleteView, TemplateView, UpdateView

from peachjam.forms import SaveDocumentForm
from peachjam.models import Folder, SavedDocument

User = get_user_model()


class BaseSavedDocumentView(PermissionRequiredMixin):
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


class SavedDocumentListView(BaseSavedDocumentView, TemplateView):
    permission_required = "peachjam.view_folder"
    context_object_name = "folders"

    def post(self, request: HttpRequest, *args, **kwargs):
        if request.htmx:
            folder_name = request.htmx.prompt
            Folder.objects.create(user=self.request.user, name=folder_name)
        context = self.get_context_data(*args, **kwargs)
        return self.render_to_response(context)


class SavedDocumentUpdateFolderView(BaseSavedDocumentView, UpdateView):
    permission_required = "peachjam.update_folder"
    model = Folder
    fields = ["name"]

    def post(self, request: HttpRequest, *args, **kwargs):
        if request.htmx:
            new_folder_name = request.htmx.prompt
            self.object = self.get_object()
            self.object.name = new_folder_name
            self.object.save()
        return self.render_to_response(self.get_context_data(*args, **kwargs))


class SavedDocumentDeleteDocumentView(BaseSavedDocumentView, DeleteView):
    permission_required = "peachjam.delete_saveddocument"
    model = SavedDocument

    def post(self, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        return self.render_to_response(self.get_context_data(**kwargs))


class SavedDocumentDeleteFolderView(BaseSavedDocumentView, DeleteView):
    permission_required = "peachjam.delete_folder"
    model = Folder

    def post(self, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        return self.render_to_response(self.get_context_data(**kwargs))


class SaveDocumentView(PermissionRequiredMixin, TemplateView):
    permission_required = "peachjam.add_saveddocument"
    template_name = "peachjam/save_document.html"

    def post(self, request: HttpRequest):
        post_data = request.POST
        instance = SavedDocument.objects.filter(
            document=post_data.get("document"),
            user=self.request.user,
        ).first()
        form = SaveDocumentForm(post_data, user=self.request.user, instance=instance)
        context = self.get_context_data()
        if form.is_valid():
            instance = form.save()
            form = SaveDocumentForm(
                document=instance.document,
                user=self.request.user,
                instance=instance,
            )
            return self.render_to_response(
                {
                    "saved_document": instance,
                    "document": instance.document,
                    "save_document_form": form,
                    "updated": True,
                    **context,
                }
            )

        return self.render_to_response({"save_document_form": form, **context})


class UnSaveDocumentView(PermissionRequiredMixin, DeleteView):
    permission_required = "peachjam.delete_saveddocument"
    template_name = "peachjam/save_document.html"
    model = SavedDocument

    def post(self, request: HttpRequest, *args, **kwargs):
        self.object = self.get_object()
        document = self.object.document
        self.object.delete()
        form = SaveDocumentForm(document=document, user=self.request.user)
        return self.render_to_response(
            {"save_document_form": form, "deleted": True, "document": document}
        )
