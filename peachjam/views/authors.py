from django.db.models import Q
from django.shortcuts import get_object_or_404

from peachjam.models import Author, CoreDocument
from peachjam.views.generic_views import FilteredDocumentListView


class AuthorDetailView(FilteredDocumentListView):
    context_object_name = "documents"
    paginate_by = 20
    model = CoreDocument
    template_name = "peachjam/author_detail.html"

    def get_base_queryset(self):
        return CoreDocument.objects.filter(
            Q(genericdocument__author=self.author)
            | Q(legalinstrument__author=self.author)
            | Q(judgment__author=self.author)
        )

    def get_queryset(self):
        self.author = get_object_or_404(Author, pk=self.kwargs["pk"])
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doc_types = list(
            set(
                self.form.filter_queryset(
                    self.get_base_queryset(), exclude="doc_type"
                ).values_list("doc_type", flat=True)
            )
        )

        context["author"] = self.author
        context["author_listing_view"] = True
        context["facet_data"]["doc_types"] = doc_types

        return context
