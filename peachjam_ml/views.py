from django.contrib.auth.mixins import PermissionRequiredMixin
from django.utils.decorators import method_decorator
from django.views.generic import DetailView

from peachjam.helpers import add_slash_to_frbr_uri
from peachjam.models import CoreDocument, Folder
from peachjam_ml.models import DocumentEmbedding


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class SimilarDocumentsView(PermissionRequiredMixin, DetailView):
    permission_required = "peachjam_ml.view_documentembedding"
    template_name = "peachjam/_similar_documents.html"
    slug_url_kwarg = "frbr_uri"
    slug_field = "expression_frbr_uri"
    model = CoreDocument

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["similar_documents"] = DocumentEmbedding.get_similar_documents(
            [self.object.pk]
        )
        return context


class SimilarDocumentsFolderView(PermissionRequiredMixin, DetailView):
    permission_required = "peachjam_ml.view_documentembedding"
    template_name = "peachjam/_similar_documents.html"
    model = Folder

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doc_ids = self.object.saved_documents.values_list("document_id", flat=True)
        context["similar_documents"] = DocumentEmbedding.get_similar_documents(doc_ids)
        return context
