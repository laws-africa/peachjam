from django import forms
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import HttpResponseBadRequest
from django.views.generic import FormView

from peachjam_ml.models import DocumentEmbedding


class SimilarDocumentsForm(forms.Form):
    doc_ids = forms.CharField(
        label="Document IDs",
        help_text="Comma-separated list of document IDs to find similar documents for.",
    )
    exclude_ids = forms.CharField(
        label="Exclude",
        help_text="Comma-separated list of document IDs to exclude from the results.",
        required=False,
    )

    def clean_doc_ids(self):
        try:
            doc_ids = self.cleaned_data["doc_ids"]
            doc_ids = [int(pk.strip()) for pk in doc_ids.split(",")]
            if not doc_ids:
                raise forms.ValidationError("Please provide at least one document ID.")
        except ValueError:
            raise forms.ValidationError(
                "Invalid document ID format. Please provide a comma-separated list of integers."
            )
        return doc_ids

    def clean_exclude_ids(self):
        exclude_ids = self.cleaned_data["exclude_ids"]
        if not exclude_ids:
            return []
        try:
            exclude_ids = [int(pk.strip()) for pk in exclude_ids.split(",")]
        except ValueError:
            raise forms.ValidationError(
                "Invalid document ID format. Please provide a comma-separated list of integers."
            )
        return exclude_ids


class SimilarDocumentsView(PermissionRequiredMixin, FormView):
    permission_required = "peachjam_ml.view_documentembedding"
    template_name = "peachjam/_similar_documents.html"
    form_class = SimilarDocumentsForm
    similarity_threshold = 0.0
    weight_similarity = 0.7
    weight_authority = 0.3
    # choose the best from this set, after re-ranking
    top_k = 100
    n_similar = 10

    def get_form(self, form_class=None):
        form_class = form_class or self.get_form_class()
        return form_class(self.request.GET)

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        doc_ids = form.cleaned_data["doc_ids"]
        exclude_ids = form.cleaned_data["exclude_ids"]
        similar_docs = DocumentEmbedding.get_similar_documents(
            doc_ids,
            exclude_ids=exclude_ids,
            threshold=self.similarity_threshold,
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

        return self.render_to_response(
            self.get_context_data(form=form, similar_documents=similar_docs)
        )

    def form_invalid(self, form):
        return HttpResponseBadRequest("Invalid form data.")
