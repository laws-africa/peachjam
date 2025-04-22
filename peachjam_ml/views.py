from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import DetailView
from pgvector.django import MaxInnerProduct

from peachjam.helpers import add_slash_to_frbr_uri
from peachjam.models import CoreDocument
from peachjam_ml.models import DocumentEmbedding


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class SimilarDocumentsView(DetailView):
    template_name = "peachjam/_similar_documents.html"
    slug_url_kwarg = "frbr_uri"
    slug_field = "expression_frbr_uri"
    model = CoreDocument

    def get_similar_documents(self):
        embedding = get_object_or_404(DocumentEmbedding, document_id=self.object.pk)
        similar_docs = (
            DocumentEmbedding.objects.exclude(document_id=self.object.pk)
            .exclude(text_embedding__isnull=True)
            .select_related("document")
            .annotate(
                similarity=MaxInnerProduct("text_embedding", embedding.text_embedding)
                * -1,
                title=F("document__title"),
                expression_frbr_uri=F("document__expression_frbr_uri"),
            )
            .values("title", "expression_frbr_uri", "similarity")
            .order_by("-similarity")[:10]
        )
        return similar_docs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["similar_documents"] = self.get_similar_documents()
        return context
