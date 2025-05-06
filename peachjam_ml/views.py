from django.contrib.auth.mixins import PermissionRequiredMixin
from django.utils.decorators import method_decorator
from django.views.generic import DetailView

from peachjam.helpers import add_slash_to_frbr_uri
from peachjam.models import CoreDocument, Folder
from peachjam_ml.models import DocumentEmbedding


class BaseSimilarDocumentsView(PermissionRequiredMixin, DetailView):
    permission_required = "peachjam_ml.view_documentembedding"
    template_name = "peachjam/_similar_documents.html"

    def get_doc_ids(self):
        raise NotImplementedError("Subclasses must implement get_doc_ids()")

    def get_similar_documents(self):
        doc_ids = self.get_doc_ids()
        similar_docs = DocumentEmbedding.get_similar_documents(doc_ids)
        return similar_docs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["similar_documents"] = self.get_similar_documents()
        return context


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class SimilarDocumentsView(BaseSimilarDocumentsView):
    slug_url_kwarg = "frbr_uri"
    slug_field = "expression_frbr_uri"
    model = CoreDocument

    def get_doc_ids(self):
        return [self.object.pk]


class SimilarDocumentsFolderView(BaseSimilarDocumentsView):
    model = Folder

    def get_doc_ids(self):
        return self.object.saved_documents.values_list("document_id", flat=True)
