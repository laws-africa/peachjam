from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from peachjam.forms import BaseDocumentFilterForm
from peachjam.models import (
    CitationLink,
    CoreDocument,
    GenericDocument,
    Judgment,
    LegalInstrument,
    Predicate,
    Relationship,
)
from peachjam.utils import add_slash, lowercase_alphabet
from peachjam_api.serializers import (
    CitationLinkSerializer,
    PredicateSerializer,
    RelationshipSerializer,
)


class FilteredDocumentListView(ListView):
    """Generic List View class for filtering documents."""

    def get(self, request, *args, **kwargs):
        self.form = BaseDocumentFilterForm(request.GET)
        self.form.is_valid()

        return super(FilteredDocumentListView, self).get(request, *args, **kwargs)

    def get_base_queryset(self):
        return self.model.objects.all()

    def get_queryset(self):
        return self.form.filter_queryset(self.get_base_queryset()).order_by("-date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Initialize facet data values
        if self.model in [GenericDocument, LegalInstrument, Judgment]:
            authors = list(
                {
                    a
                    for a in self.form.filter_queryset(
                        self.get_base_queryset(), exclude="author"
                    ).values_list("author__name", flat=True)
                    if a
                }
            )
        # Legislation objects don't have an associated author, hence empty authors list
        else:
            authors = []

        years = list(
            set(
                self.form.filter_queryset(
                    self.get_base_queryset(), exclude="year"
                ).values_list("date__year", flat=True)
            )
        )

        context["facet_data"] = {
            "years": years,
            "authors": authors,
            "alphabet": lowercase_alphabet(),
        }
        return context


class BaseDocumentDetailView(DetailView):
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "frbr_uri"
    context_object_name = "document"

    def get_object(self, *args, **kwargs):
        return self.model.objects.get(
            expression_frbr_uri=add_slash(self.kwargs.get("frbr_uri"))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # get all versions that match current document work_frbr_uri
        all_versions = CoreDocument.objects.filter(
            work_frbr_uri=self.object.work_frbr_uri
        ).exclude(pk=self.object.pk)

        # citation links for a document
        doc = get_object_or_404(CoreDocument, pk=self.object.pk)
        citation_links = CitationLink.objects.filter(document=doc)
        context["citation_links"] = CitationLinkSerializer(
            citation_links, many=True
        ).data

        # language versions that match current document date
        context["language_versions"] = all_versions.filter(date=self.object.date)

        # date versions that match current document language
        context["date_versions"] = all_versions.filter(
            language=self.object.language
        ).order_by("-date")

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

        if self.request.user.has_perm("peachjam.add_relationship"):
            context["predicates_json"] = PredicateSerializer(
                Predicate.objects.all(), many=True
            ).data

        if context["document"].content_html:
            context["display_type"] = (
                "akn" if context["document"].content_html_is_akn else "html"
            )
        elif hasattr(context["document"], "source_file"):
            context["display_type"] = "pdf"
        else:
            context["display_type"] = None

        return context
