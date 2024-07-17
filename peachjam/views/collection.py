from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from peachjam.forms import CollectionForm, SaveDocumentForm
from peachjam.models import SavedDocument, UserProfile

User = get_user_model()


class CreateCollectionView(TemplateView):
    template_name = "peachjam/collections_list.html"

    def post(self, request: HttpRequest):
        post_data = request.POST
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        form = CollectionForm(post_data, user_profile=user_profile)
        context = self.get_context_data()
        if form.is_valid():
            instance = form.save()
            return self.render_to_response(
                {
                    "saved_document": instance,
                    "add_new_collection_form": form,
                    **context,
                }
            )

        return self.render_to_response({"add_new_collection_form": form, **context})


class SaveDocumentView(TemplateView):
    template_name = "peachjam/save_document.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        user_profile = get_object_or_404(UserProfile, user=self.request.user)
        collections = user_profile.collections.all()
        context["collections"] = collections
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
            return self.render_to_response(
                {"saved_document": instance, "save_document_form": form, **context}
            )

        return self.render_to_response({"save_document_form": form, **context})
