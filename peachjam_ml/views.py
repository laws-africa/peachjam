from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import DetailView
from pgvector.django import MaxInnerProduct

from peachjam.helpers import add_slash_to_frbr_uri
from peachjam.models import CoreDocument
from peachjam_ml.models import DocumentEmbedding


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class SimilarDocumentsView(PermissionRequiredMixin, DetailView):
    permission_required = "peachjam_ml.view_documentembedding"
    template_name = "peachjam/_similar_documents.html"
    slug_url_kwarg = "frbr_uri"
    slug_field = "expression_frbr_uri"
    model = CoreDocument
    similarity_threshold = 0.0
    weight_similarity = 0.7
    weight_authority = 0.3
    # choose the best from this set, after re-ranking
    top_k = 100
    n_similar = 10

    def get_similar_documents(self):
        embedding = get_object_or_404(DocumentEmbedding, document_id=self.object.pk)
        similar_docs = (
            DocumentEmbedding.objects.exclude(document__work=self.object.work)
            .exclude(text_embedding__isnull=True)
            .select_related("document")
            .annotate(
                similarity=MaxInnerProduct("text_embedding", embedding.text_embedding)
                * -1,
                title=F("document__title"),
                expression_frbr_uri=F("document__expression_frbr_uri"),
                authority_score=F("document__work__authority_score"),
            )
            .filter(similarity__gt=self.similarity_threshold)
            .values("title", "expression_frbr_uri", "similarity", "authority_score")
            .order_by("-similarity")
        )[: self.top_k]

        # re-rank based on a weighted average of similarity and authority score, and keep the top 10
        similar_docs = sorted(
            similar_docs,
            key=lambda x: (
                x["similarity"] * self.weight_similarity
                + x["authority_score"] * self.weight_authority
            ),
            reverse=True,
        )[: self.n_similar]

        return similar_docs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["similar_documents"] = self.get_similar_documents()
        return context
