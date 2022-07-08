from django.http import QueryDict
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from africanlii.forms import BaseDocumentFilterForm
from africanlii.utils import lowercase_alphabet
from peachjam.models import CitationLink, CoreDocument, Predicate, Relationship
from peachjam_api.serializers import (
    CitationLinkSerializer,
    PredicateSerializer,
    RelationshipSerializer,
)


class FilteredDocumentListView(ListView, BaseDocumentFilterForm):
    """Generic List View class for filtering documents."""

    def get_queryset(self):
        self.form = BaseDocumentFilterForm(self.request.GET)
        self.form.is_valid()
        queryset = self.model.objects.all()
        return self.form.filter_queryset(queryset)

    def get_context_data(self, **kwargs):
        context = super(FilteredDocumentListView, self).get_context_data(**kwargs)

        # Initialize facet_data values i.e years and authors
        years = list(set(self.model.objects.values_list("date__year", flat=True)))

        object_doc_type = self.model.objects.values_list("doc_type", flat=True)
        if object_doc_type and "legislation" not in object_doc_type:
            authors = list(
                {
                    a
                    for a in self.model.objects.values_list("author__name", flat=True)
                    if a
                }
            )
        # Legislation objects don't have an associated author, hence empty authors list
        else:
            authors = []

        # Read parameter values
        params = QueryDict(mutable=True)
        params.update(self.request.GET)

        year = params.get("year")
        author = params.get("author")
        alphabet = params.get("alphabet")

        # Use parameter values to filter
        if year:
            # TODO: apply all filters except year
            years = list(
                set(
                    self.model.objects.filter(date__year=year).values_list(
                        "date__year", flat=True
                    )
                )
            )

        if author:
            authors = list(
                set(
                    self.model.objects.filter(author__name=author).values_list(
                        "author__name", flat=True
                    )
                )
            )

        if alphabet:
            documents = self.get_queryset().filter(title__istartswith=alphabet)
            years = list(set(documents.values_list("date__year", flat=True)))
            authors = list(set(documents.values_list("author__name", flat=True)))
            context["documents"] = documents

        context["facet_data"] = {
            "years": years,
            "authors": authors,
            "alphabet": lowercase_alphabet(),
        }
        return context


class BaseDocumentDetailView(DetailView):
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "expression_frbr_uri"
    context_object_name = "document"

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

        return context
