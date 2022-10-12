from django.db.models import Q
from django.shortcuts import get_object_or_404

from peachjam.models import CoreDocument, Court
from peachjam.views.generic_views import FilteredDocumentListView


class CourtDetailView(FilteredDocumentListView):
    template_name = "peachjam/court_detail.html"

    def get_base_queryset(self):
        return CoreDocument.objects.filter(Q(judgment__court=self.court))

    def get_queryset(self):
        self.court = get_object_or_404(Court, code=self.kwargs["code"])
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

        context["court"] = self.court
        context["author_listing_view"] = True
        context["facet_data"]["doc_types"] = doc_types

        return context
