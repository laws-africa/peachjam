from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from peachjam.forms import FolderForm, SaveDocumentForm
from peachjam.models import CoreDocument, SavedDocument, UserProfile

User = get_user_model()


class CreateFolderView(PermissionRequiredMixin, TemplateView):
    permission_required = "peachjam.add_folder"
    template_name = "peachjam/folders_list.html"

    def post(self, request: HttpRequest):
        post_data = request.POST
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        form = FolderForm(post_data, user_profile=user_profile)
        context = self.get_context_data()
        if form.is_valid():
            instance = form.save()
            return self.render_to_response(
                {
                    "folder": instance,
                    "folder_form": form,
                    **context,
                }
            )

        return self.render_to_response({"folder_form": form, **context})

    def get(self, *args, **kwargs):
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        form = FolderForm(user_profile=user_profile)

        return self.render_to_response({"folder_form": form})


class SaveDocumentView(PermissionRequiredMixin, TemplateView):
    permission_required = "peachjam.add_saveddocument"
    template_name = "peachjam/save_document.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        folders = user_profile.folders.all()
        context["folders"] = folders
        return context

    def post(self, request: HttpRequest):
        post_data = request.POST
        instance = SavedDocument.objects.filter(
            document=post_data.get("document"),
            user_profile=post_data.get("user_profile"),
        ).first()
        form = SaveDocumentForm(post_data, instance=instance)
        context = self.get_context_data()
        if form.is_valid():
            instance = form.save()
            form = SaveDocumentForm(
                document=instance.document,
                user_profile=instance.user_profile,
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

    def delete(self, request: HttpRequest):
        data = request.GET
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        document = get_object_or_404(CoreDocument, pk=data["document"])
        form = SaveDocumentForm(document=document, user_profile=user_profile)

        if data.get("id"):
            instance = SavedDocument.objects.filter(pk=data.get("id")).first()
            instance.delete()

        return self.render_to_response(
            {"save_document_form": form, "deleted": True, "document": document}
        )
