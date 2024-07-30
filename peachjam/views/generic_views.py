import itertools

from django.http.response import HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils.dates import MONTHS
from django.utils.text import gettext_lazy as _
from django.views.generic import DetailView, ListView, View
from lxml import html

from peachjam.forms import BaseDocumentFilterForm
from peachjam.helpers import add_slash, get_language, lowercase_alphabet
from peachjam.models import (
    Author,
    CitationLink,
    CoreDocument,
    GenericDocument,
    LegalInstrument,
    Predicate,
    Relationship,
)
from peachjam_api.serializers import (
    CitationLinkSerializer,
    PredicateSerializer,
    RelationshipSerializer,
)


class DocumentListView(ListView):
    """Generic list view for document lists."""

    context_object_name = "documents"
    paginate_by = 50
    model = CoreDocument
    queryset = CoreDocument.objects.select_related(
        "nature",
        "work",
        "jurisdiction",
        "locality",
    ).prefetch_related("labels")

    # when grouping by date, group by year, or month and year? ("year" and "month-year" are the only options)
    group_by_date = "year"

    def get_base_queryset(self, *args, **kwargs):
        qs = self.queryset if self.queryset is not None else self.model.objects
        return qs.filter(published=True)

    def get_queryset(self):
        qs = self.get_base_queryset()
        return qs.preferred_language(get_language(self.request))

    def get_context_data(self, *args, **kwargs):
        return super().get_context_data(
            doc_table_show_jurisdiction=True, *args, **kwargs
        )

    def group_documents(self, documents, group_by):
        if not group_by:
            return documents

        def grouper(d):
            if group_by == "date":
                if self.group_by_date == "month-year":
                    return f"{MONTHS[d.date.month]} {d.date.year}"
                else:
                    return d.date.year
            elif group_by == "title":
                return d.title[0].upper()

        class Group:
            is_group = True

            def __init__(self, title):
                self.title = title

        docs = []
        for key, group in itertools.groupby(documents, grouper):
            docs.append(Group(key))
            docs.extend(group)

        return docs

    def get_template_names(self):
        if self.request.htmx:
            if self.request.htmx.target == "doc-table":
                return ["peachjam/_document_table.html"]
            return ["peachjam/_document_table_form.html"]
        return super().get_template_names()


class FilteredDocumentListView(DocumentListView):
    """Generic list view for filtered document lists."""

    form_class = BaseDocumentFilterForm
    # Should the listing filter to include only the latest expressions of a document?
    # This is a bit more expensive and so is opt-in. It is only necessary for document types
    # that have multiple points-in-time (dated expressions), such as Legislation.
    latest_expression_only = False
    # default values to pre-populate the form with
    form_defaults = None

    def get(self, request, *args, **kwargs):
        self.form = self.get_form()
        self.form.is_valid()
        return super().get(request, *args, **kwargs)

    def get_form(self):
        return self.form_class(self.form_defaults, self.request.GET)

    def get_queryset(self):
        qs = super().get_queryset()
        # filter the queryset, including filtering on the form's query string
        filtered_qs = self.filter_queryset(qs, filter_q=True)

        if self.latest_expression_only:
            # Getting only the latest expression requires ordering on the work, which breaks the actual ordering
            # we want on the results. So, we take the filtered queryset and move that into a subquery,
            # and then apply the normal ordering on a fresh copy of the main queryset.

            # first, do the latest expression filtering
            filtered_qs = filtered_qs.order_by().latest_expression()
            # now move that into a subquery on the unfiltered queryset -- the filtering will come from the subquery
            filtered_qs = qs.filter(pk__in=filtered_qs.values("id"))
            # now apply the standard ordering
            filtered_qs = self.form.order_queryset(filtered_qs)

        return filtered_qs

    def filter_queryset(self, qs, filter_q=False):
        return self.form.filter_queryset(qs, filter_q=filter_q)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(form=self.form, **kwargs)

        self.add_facets(context)
        self.show_facet_clear_all(context)
        context["doc_count"] = context["paginator"].count

        return context

    def add_facets(self, context):
        authors = []
        # Initialize facet data values
        natures = list(
            doc_n
            for doc_n in self.form.filter_queryset(
                self.get_base_queryset(), exclude="natures"
            )
            .order_by()
            .values_list("nature__name", flat=True)
            .distinct()
            if doc_n
        )
        if self.model in [GenericDocument, LegalInstrument]:
            authors = list(
                a
                for a in self.form.filter_queryset(
                    self.get_base_queryset(), exclude="authors"
                )
                .order_by()
                .values_list("authors__name", flat=True)
                .distinct()
                if a
            )

        years = list(
            self.form.filter_queryset(self.get_base_queryset(), exclude="years")
            .order_by()
            .values_list("date__year", flat=True)
            .distinct()
        )
        taxonomies = list(
            self.form.filter_queryset(self.get_base_queryset(), exclude="taxonomies")
            .filter(taxonomies__topic__isnull=False)
            .order_by("taxonomies__topic__name")
            .values_list("taxonomies__topic__name", flat=True)
            .distinct()
        )

        context["doc_table_show_author"] = bool(authors)
        context["doc_table_show_doc_type"] = bool(natures)
        context["facet_data"] = {
            "years": {
                "label": _("Years"),
                "type": "checkbox",
                "options": [str(y) for y in sorted(years, reverse=True)],
                "values": self.request.GET.getlist("years"),
            },
            "authors": {
                "label": Author.model_label_plural,
                "type": "checkbox",
                "options": authors,
                "values": self.request.GET.getlist("authors"),
            },
            "natures": {
                "label": _("Document nature"),
                "type": "radio",
                "options": natures,
                "values": self.request.GET.getlist("natures"),
            },
            "taxonomies": {
                "label": _("Topics"),
                "type": "checkbox",
                "options": taxonomies,
                "values": self.request.GET.getlist("taxonomies"),
            },
            "alphabet": {
                "label": _("Alphabet"),
                "type": "radio",
                "options": lowercase_alphabet(),
                "values": self.request.GET.get("alphabet"),
            },
        }

    def show_facet_clear_all(self, context):
        context["show_clear_all"] = any(
            [f["values"] for f in context["facet_data"].values()]
        )

    def group_documents(self, documents, group_by=None):
        # determine what to group by
        if group_by is None:
            group_by = documents.query.order_by[0]
            if group_by.startswith("-"):
                group_by = group_by[1:]

        return super().group_documents(documents, group_by)


class BaseDocumentDetailView(DetailView):
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "frbr_uri"
    context_object_name = "document"
    document_diffs_url = "https://services.lawsafrica.com"

    def get_object(self, *args, **kwargs):
        return get_object_or_404(
            self.model, expression_frbr_uri=add_slash(self.kwargs.get("frbr_uri"))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(
            document_diffs_url=self.document_diffs_url, **kwargs
        )

        # citation links for a document
        doc = get_object_or_404(CoreDocument, pk=self.object.pk)
        citation_links = CitationLink.objects.filter(document=doc)
        context["citation_links"] = CitationLinkSerializer(
            citation_links, many=True
        ).data

        # get all versions that match current document work_frbr_uri
        all_versions = CoreDocument.objects.filter(
            work_frbr_uri=self.object.work_frbr_uri
        )
        # language versions that match current document date
        context["language_versions"] = all_versions.filter(date=self.object.date)

        # date versions that match current document language
        context["date_versions"] = all_versions.filter(
            language=self.object.language
        ).order_by("-date")

        self.add_relationships(context)
        self.add_provision_relationships(context)

        if context["document"].content_html:
            context["display_type"] = (
                "akn" if context["document"].content_html_is_akn else "html"
            )
            if not context["document"].content_html_is_akn:
                self.prefix_images(context["document"])
        elif hasattr(context["document"], "source_file"):
            context["display_type"] = "pdf"
        else:
            context["display_type"] = None

        context["notices"] = self.get_notices()
        context["taxonomies"] = doc.taxonomies.prefetch_related("topic")
        context["labels"] = doc.labels.all()

        # citations
        context["cited_documents"] = self.fetch_citation_docs(doc.work.cited_works())
        context["documents_citing_current_doc"] = self.fetch_citation_docs(
            doc.work.works_citing_current_work()
        )

        return context

    def fetch_citation_docs(self, works):
        docs = sorted(
            list(
                CoreDocument.objects.prefetch_related("work")
                .select_related("nature")
                .filter(work__in=works)
                .distinct("work_frbr_uri")
                .order_by("work_frbr_uri", "-date")
                .preferred_language(get_language(self.request))
            ),
            key=lambda d: d.get_doc_type_display(),
        )

        grouped_docs = itertools.groupby(docs, lambda d: d.get_doc_type_display())

        result = [
            {
                "doc_type": doc_type,
                # sort by citations descending, then title
                "docs": sorted(
                    list(group), key=lambda d: [-d.work.n_citing_works, d.title]
                ),
            }
            for doc_type, group in grouped_docs
        ]

        # sort by size of group, descending
        result.sort(key=lambda g: -len(g["docs"]))

        return result

    def add_relationships(self, context):
        # sort and group by predicate
        rels_as_subject = sorted(
            list(
                Relationship.for_subject_document(context["document"])
                .filter(object_work__documents__isnull=False)
                .distinct("pk")
            ),
            key=lambda r: [r.predicate.verb, r.object_work.title],
        )
        rels_as_subject = [
            (verb, list(group))
            for verb, group in itertools.groupby(
                rels_as_subject, lambda r: r.predicate.verb
            )
        ]

        # sort and group by predicate
        rels_as_object = sorted(
            list(
                Relationship.for_object_document(context["document"])
                .filter(subject_work__documents__isnull=False)
                .distinct("pk")
            ),
            key=lambda r: [r.predicate.reverse_verb, r.subject_work.title],
        )
        rels_as_object = [
            (verb, list(group))
            for verb, group in itertools.groupby(
                rels_as_object, lambda r: r.predicate.reverse_verb
            )
        ]

        context["relationships_as_subject"] = rels_as_subject
        context["relationships_as_object"] = rels_as_object
        context["n_relationships"] = sum(
            len(g) for v, g in itertools.chain(rels_as_object, rels_as_subject)
        )
        context["relationship_limit"] = 4

    def add_provision_relationships(self, context):
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

    def get_notices(self):
        return []

    def prefix_images(self, document):
        """Rewrite image URLs so that we can serve them correctly."""
        root = html.fromstring(document.content_html)

        for img in root.xpath(".//img[@src]"):
            src = img.attrib["src"]
            if not src.startswith("/") and not src.startswith("data:"):
                img.attrib["src"] = (
                    document.expression_frbr_uri + "/media/" + img.attrib["src"]
                )

        document.content_html = html.tostring(root, encoding="unicode")


class CSRFTokenView(View):
    """This view returns a CSRF token for use with the API."""

    def get(self, request, *args, **kwargs):
        return HttpResponse(get_token(request), content_type="text/plain")
