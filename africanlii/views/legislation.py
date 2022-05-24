from django.views.generic import DetailView

from africanlii.models import Legislation
from africanlii.registry import registry
from africanlii.views.generic_views import FilteredDocumentListView
from peachjam.models import Relationship
from peachjam.views import AuthedViewMixin
from peachjam_api.serializers import RelationshipSerializer


class LegislationListView(AuthedViewMixin, FilteredDocumentListView):
    model = Legislation
    template_name = "africanlii/legislation_list.html"
    context_object_name = "documents"
    paginate_by = 20


@registry.register_doc_type("legislation")
class LegislationDetailView(AuthedViewMixin, DetailView):
    model = Legislation
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "expression_frbr_uri"
    template_name = "africanlii/legislation_detail.html"
    context_object_name = "document"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # provision relationships
        rels = [
            r
            for r in Relationship.for_subject_document(
                context["document"]
            ).prefetch_related(
                "subject_work",
                "subject_work__documents",
                "object_work",
                "object_work__documents",
            )
            if r.subject_target_id
        ] + [
            r
            for r in Relationship.for_object_document(
                context["document"]
            ).prefetch_related(
                "subject_work",
                "subject_work__documents",
                "object_work",
                "object_work__documents",
            )
            if r.object_target_id
        ]
        context["provision_relationships"] = RelationshipSerializer(
            rels, many=True
        ).data

        return context
