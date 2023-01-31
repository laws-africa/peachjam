from peachjam.models import Judgment
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class JudgmentListView(FilteredDocumentListView):
    model = Judgment
    template_name = "peachjam/judgment_list.html"
    navbar_link = "judgments"
    queryset = Judgment.objects.prefetch_related("work")

    def get_queryset(self):
        queryset = super(JudgmentListView, self).get_queryset()
        return queryset.order_by("-date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["doc_table_show_court"] = True
        return context


@registry.register_doc_type("judgment")
class JudgmentDetailView(BaseDocumentDetailView):
    model = Judgment
    template_name = "peachjam/judgment_detail.html"
