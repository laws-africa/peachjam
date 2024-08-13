from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from peachjam.forms import SaveDocumentForm
from peachjam.models import CoreDocument, Folder, SavedDocument, UserProfile

User = get_user_model()


class SavedDocumentListView(TemplateView):
    template_name = "peachjam/saved_document_list.html"
    context_object_name = "folders"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        context["ungrouped_saved_documents"] = user_profile.saved_documents.filter(
            folder__isnull=True
        )
        context["folders"] = user_profile.folders.all()
        return context

    def get_template_names(self):
        if self.request.htmx:
            return ["peachjam/_folders_list.html"]
        return ["peachjam/saved_document_list.html"]

    def delete(self, request: HttpRequest, *args, **kwargs):
        data = request.GET

        if data.get("folder_id"):
            instance = Folder.objects.filter(pk=data["folder_id"]).first()
            if instance:
                instance.delete()
        elif data.get("saved_doc_id"):
            instance = SavedDocument.objects.filter(pk=data["saved_doc_id"]).first()
            if instance:
                instance.delete()

        context = self.get_context_data(*args, **kwargs)

        return self.render_to_response({"deleted": True, **context})

    def put(self, request: HttpRequest, *args, **kwargs):
        data = request.GET
        if request.htmx and data.get("folder_id"):
            new_folder_name = request.htmx.prompt
            folder = Folder.objects.filter(pk=data["folder_id"]).first()
            if folder:
                folder.name = new_folder_name
                folder.save()
        context = self.get_context_data(*args, **kwargs)

        return self.render_to_response(context)

    def post(self, request: HttpRequest, *args, **kwargs):
        if request.htmx:
            folder_name = request.htmx.prompt
            user_profile = get_object_or_404(UserProfile, user=self.request.user)
            Folder.objects.create(user_profile=user_profile, name=folder_name)
        context = self.get_context_data(*args, **kwargs)
        return self.render_to_response(context)


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
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        instance = SavedDocument.objects.filter(
            document=post_data.get("document"),
            user_profile=user_profile,
        ).first()
        form = SaveDocumentForm(post_data, user_profile=user_profile, instance=instance)
        context = self.get_context_data()
        if form.is_valid():
            instance = form.save()
            form = SaveDocumentForm(
                document=instance.document,
                user_profile=user_profile,
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
        if data.get("document"):
            document = get_object_or_404(CoreDocument, pk=data["document"])
            form = SaveDocumentForm(document=document, user_profile=user_profile)

            if data.get("id"):
                instance = SavedDocument.objects.filter(pk=data.get("id")).first()
                if instance:
                    instance.delete()

            return self.render_to_response(
                {"save_document_form": form, "deleted": True, "document": document}
            )

        return self.render_to_response({"deleted": False})
