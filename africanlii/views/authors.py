from django.db.models import Q
from django.shortcuts import get_object_or_404

from africanlii.views import FilteredDocumentListView
from peachjam.models import Author, CoreDocument


class AuthorListView(FilteredDocumentListView):
    context_object_name = "documents"
    paginate_by = 20
    model = Author
    template_name = "africanlii/_author_detail.html"

    def get_queryset(self):
        super().get_queryset()
        self.author = get_object_or_404(self.model, pk=self.kwargs["pk"])

        queryset = CoreDocument.objects.filter(
            Q(genericdocument__author=self.author)
            | Q(legalinstrument__author=self.author)
            | Q(judgment__author=self.author)
        )

        return self.form.filter_queryset(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Fetch the author's documents
        docs = CoreDocument.objects.filter(
            Q(genericdocument__author=self.author)
            | Q(legalinstrument__author=self.author)
            | Q(judgment__author=self.author)
        )

        doc_types = list(
            set(
                self.form.filter_queryset(docs, exclude="doc_type").values_list(
                    "doc_type", flat=True
                )
            )
        )

        context["author"] = self.author
        context["author_listing_view"] = True
        context["facet_data"]["doc_types"] = doc_types

        return context
