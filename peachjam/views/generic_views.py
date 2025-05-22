import itertools

from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count
from django.dispatch import Signal
from django.http import Http404
from django.http.response import HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils.dates import MONTHS
from django.utils.functional import cached_property
from django.utils.text import gettext_lazy as _
from django.views.generic import DetailView, ListView, View
from lxml import html

from peachjam.customerio import get_customerio
from peachjam.forms import BaseDocumentFilterForm
from peachjam.helpers import add_slash, get_language, lowercase_alphabet
from peachjam.models import (
    Author,
    CitationLink,
    CoreDocument,
    DocumentNature,
    ExtractedCitation,
    Predicate,
    Relationship,
    Taxonomy,
    UnconstitutionalProvision,
    pj_settings,
)
from peachjam_api.serializers import (
    CitationLinkSerializer,
    PredicateSerializer,
    RelationshipSerializer,
    UnconstitutionalProvisionsSerializer,
)


class ClampedPaginator(Paginator):
    """A paginator that clamps the maximum number of pages. This is useful when dealing with very large datasets,
    because PostgreSQL's OFFSET-based pagination is very slow for large datasets.

    See:

    * https://readyset.io/blog/optimizing-sql-pagination-in-postgres
    * https://github.com/photocrowd/django-cursor-pagination
    """

    def __init__(self, *args, **kwargs):
        cache_key_prefix = kwargs.pop("cache_key_prefix")
        self.cache_key = f"{cache_key_prefix}_doc_count"
        super().__init__(*args, **kwargs)

    max_num_pages = 10

    @cached_property
    def num_pages(self):
        return min(super().num_pages, self.max_num_pages)

    @cached_property
    def count(self):
        doc_count = cache.get(self.cache_key)
        if doc_count is None:
            doc_count = super().count
            cache.set(self.cache_key, doc_count)
        return doc_count


class DocumentListView(ListView):
    """Generic list view for document lists."""

    context_object_name = "documents"
    paginate_by = 50
    paginator_class = ClampedPaginator
    model = CoreDocument

    # when grouping by date, group by year, or month and year? ("year" and "month-year" are the only options)
    group_by_date = "year"

    def get_paginator(
        self, queryset, per_page, orphans=0, allow_empty_first_page=True, **kwargs
    ):
        return self.paginator_class(
            queryset,
            per_page,
            orphans=orphans,
            allow_empty_first_page=allow_empty_first_page,
            cache_key_prefix=self.cache_key_prefix(),
            **kwargs,
        )

    def cache_key_prefix(self):
        return self.request.get_full_path()

    def get_model_queryset(self):
        qs = self.queryset if self.queryset is not None else self.model.objects
        return qs.filter(published=True).for_document_table()

    def get_base_queryset(self, *args, **kwargs):
        return self.get_model_queryset()

    def get_queryset(self):
        qs = self.get_base_queryset()
        return qs.preferred_language(get_language(self.request))

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(
            doc_table_show_jurisdiction=True,
            doc_table_show_date=True,
            doc_count_noun=_("document"),
            doc_count_noun_plural=_("documents"),
            *args,
            **kwargs,
        )
        self.add_entity_profile(context)
        return context

    def add_entity_profile(self, context):
        pass

    def group_documents(self, documents, group_by):
        if not group_by:
            return documents

        class Group:
            is_group = True

            def __init__(self, title):
                self.title = title
                if group_by == "date":
                    title = title.split()
                    if len(title) == 2:
                        self.group_id = title[0]
                        self.title = f"{MONTHS[int(title[0])]} {title[1]}"

        docs = []
        for key, group in itertools.groupby(
            documents, lambda d: self.get_document_group(group_by, d)
        ):
            docs.append(Group(key))
            docs.extend(group)

        return docs

    def get_document_group(self, group_by, document):
        if group_by == "date":
            if self.group_by_date == "month-year":
                return f"{document.date.month} {document.date.year}"
            else:
                return f"{document.date.year}"
        elif group_by == "title":
            return document.title[0].upper()

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
    exclude_facets = []

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

    def doc_count(self, context):
        if context["paginator"]:
            count = context["paginator"].count
        else:
            key = f"{self.cache_key_prefix()}_doc_count"
            count = cache.get(key)
            if count is None:
                count = context["object_list"].count()
                cache.set(key, count)
        context["doc_count"] = count

    def get_context_data(self, **kwargs):
        context = super().get_context_data(form=self.form, **kwargs)

        self.add_facets(context)
        self.show_facet_clear_all(context)
        self.doc_count(context)
        context["doc_table_title_label"] = _("Title")
        context["doc_table_date_label"] = _("Date")

        return context

    def add_taxonomies_facet(self, context):
        if "taxonomies" not in self.exclude_facets:
            taxonomies = Taxonomy.objects.filter(
                pk__in=self.form.filter_queryset(
                    self.get_base_queryset(), exclude="taxonomies"
                )
                .filter(taxonomies__topic__isnull=False)
                .order_by("taxonomies__topic__id")
                .values_list("taxonomies__topic__id", flat=True)
                .distinct()
            )
            if taxonomies:
                context["facet_data"]["taxonomies"] = {
                    "label": _("Topics"),
                    "type": "checkbox",
                    "options": sorted(
                        [(t.slug, t.name) for t in taxonomies], key=lambda x: x[1]
                    ),
                    "values": self.request.GET.getlist("taxonomies"),
                }

    def add_alphabet_facet(self, context):
        if "alphabet" not in self.exclude_facets:
            context["facet_data"]["alphabet"] = {
                "label": _("Alphabet"),
                "type": "radio",
                "options": [(a, a) for a in lowercase_alphabet()],
                "values": self.request.GET.get("alphabet"),
            }

    def add_natures_facet(self, context):
        if "natures" not in self.exclude_facets:
            natures = DocumentNature.objects.filter(
                pk__in=self.form.filter_queryset(
                    self.get_base_queryset(), exclude="natures"
                )
                .order_by()
                .values_list("nature_id", flat=True)
                .distinct()
            )
            context["doc_table_show_doc_type"] = bool(natures)
            if natures.count() > 1:
                context["facet_data"]["natures"] = {
                    "label": _("Document nature"),
                    "type": "radio",
                    # this ensures we get the translated name
                    "options": sorted(
                        [(n.code, n.name) for n in natures], key=lambda x: x[1]
                    ),
                    "values": self.request.GET.getlist("natures"),
                }

    def add_authors_facet(self, context):
        if "authors" not in self.exclude_facets:
            authors = []
            authors_label = Author.model_label_plural
            if hasattr(self.model, "author"):
                authors = list(
                    a
                    for a in self.form.filter_queryset(
                        self.get_base_queryset(), exclude="authors"
                    )
                    .order_by()
                    .values_list("author__name", flat=True)
                    .distinct()
                    if a
                )
                context["doc_table_show_author"] = bool(authors)
                # customise the authors label?
                if authors:
                    authors_label = getattr(
                        self.model, "author_label_plural", authors_label
                    )
                    context["facet_data"]["authors"] = {
                        "label": authors_label,
                        "type": "checkbox",
                        "options": sorted([(a, a) for a in authors]),
                        "values": self.request.GET.getlist("authors"),
                    }

    def add_years_facet(self, context):
        if "years" not in self.exclude_facets:
            years = list(
                self.form.filter_queryset(self.get_base_queryset(), exclude="years")
                .order_by()
                .values_list("date__year", flat=True)
                .distinct()
            )
            if years:
                context["facet_data"]["years"] = {
                    "label": _("Years"),
                    "type": "checkbox",
                    # these are (value, label) tuples
                    "options": [(str(y), y) for y in sorted(years, reverse=True)],
                    "values": self.request.GET.getlist("years"),
                }

    def add_facets(self, context):
        context["facet_data"] = {}
        self.add_years_facet(context)
        self.add_authors_facet(context)
        self.add_natures_facet(context)
        self.add_taxonomies_facet(context)
        self.add_alphabet_facet(context)

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
    modify_context = Signal()

    def get_object(self, *args, **kwargs):
        return get_object_or_404(
            self.model, expression_frbr_uri=add_slash(self.kwargs.get("frbr_uri"))
        )

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .prefetch_related("custom_properties", "taxonomies__topic")
        )

    def show_save_doc_button(self):
        return pj_settings().allow_save_documents and (
            not self.request.user.is_authenticated
            or self.request.user.has_perm("peachjam.add_saveddocument")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(
            document_diffs_url=self.document_diffs_url, **kwargs
        )

        # citation links for a document
        doc = self.object
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
        self.add_unconstitutional_provisions(context)

        if context["document"].content_html:
            context["display_type"] = (
                "akn" if context["document"].content_html_is_akn else "html"
            )
            self.prefix_images(context["document"])
        elif hasattr(context["document"], "source_file"):
            context["display_type"] = "pdf"
        else:
            context["display_type"] = None

        context["notices"] = self.get_notices()
        context["taxonomies"] = Taxonomy.get_tree_for_items(
            Taxonomy.objects.filter(
                pk__in=doc.taxonomies.values_list("topic__pk", flat=True)
            )
        )
        context["labels"] = doc.labels.all()

        # citations
        context["cited_documents"] = self.fetch_citation_docs(
            doc.work.cited_works(), "cited_works"
        )
        context["documents_citing_current_doc"] = self.fetch_citation_docs(
            doc.work.works_citing_current_work(), "citing_works"
        )
        context["show_save_doc_button"] = self.show_save_doc_button()

        # provide extra context for analytics
        self.add_track_page_properties(context)
        self.modify_context.send(sender=self.__class__, context=context, view=self)
        return context

    def fetch_citation_docs(self, works, direction):
        """Fetch documents for the given works, grouped by nature and ordered by the most incoming citations."""
        # count the number of unique works, grouping by nature
        counts = {
            r["nature"]: r["n"]
            for r in CoreDocument.objects.filter(work__in=works)
            .values("nature")
            .annotate(n=Count("work_frbr_uri", distinct=True))
        }

        # get the top 10 documents for each nature, ordering by the number of incoming citations
        docs, truncated = ExtractedCitation.fetch_grouped_citation_docs(
            works, get_language(self.request)
        )

        table_direction = None
        if direction == "cited_works":
            table_direction = "outgoing"
            citations = ExtractedCitation.objects.filter(
                citing_work=self.object.work, target_work__documents__in=docs
            ).prefetch_related("treatments")
            treatments = {c.target_work_id: c.treatments for c in citations}

        elif direction == "citing_works":
            table_direction = "incoming"
            citations = ExtractedCitation.objects.filter(
                citing_work__documents__in=docs, target_work=self.object.work
            ).prefetch_related("treatments")
            treatments = {c.citing_work_id: c.treatments for c in citations}

        for d in docs:
            treatment = treatments.get(d.work.pk, [])
            setattr(d, "treatments", treatment)

        result = [
            {
                "nature": nature,
                "n_docs": counts.get(nature.pk, 0),
                "docs": list(group),
                "table_id": f"citations-table-{table_direction}-{nature.pk}",
            }
            # the docs are already sorted by nature
            for nature, group in itertools.groupby(docs, lambda d: d.nature)
        ]

        # sort by size of group, descending
        result.sort(key=lambda g: -g["n_docs"])

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
        context["show_related_documents"] = context["n_relationships"] > 0
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

    def add_unconstitutional_provisions(self, context):
        unconstitutional_provisions = list(
            UnconstitutionalProvision.objects.filter(work=self.object.work)
        )
        for provision in unconstitutional_provisions:
            provision.document = self.object

        context["unconstitutional_provisions"] = unconstitutional_provisions
        context[
            "unconstitutional_provisions_json"
        ] = UnconstitutionalProvisionsSerializer(
            unconstitutional_provisions, many=True
        ).data

    def get_notices(self):
        return []

    def prefix_images(self, document):
        """Rewrite image URLs so that we can serve them correctly."""
        root = document.content_html_tree

        for img in root.xpath(".//img[@src]"):
            src = img.attrib["src"]
            if not src.startswith("/") and not src.startswith("data:"):
                if not src.startswith("media/"):
                    src = "media/" + src
                img.attrib["src"] = document.expression_frbr_uri + "/" + src

        document.content_html = html.tostring(root, encoding="unicode")

    def add_track_page_properties(self, context):
        context[
            "track_page_properties"
        ] = get_customerio().get_document_track_properties(context["document"])


class CSRFTokenView(View):
    """This view returns a CSRF token for use with the API."""

    def get(self, request, *args, **kwargs):
        return HttpResponse(get_token(request), content_type="text/plain")


class YearMixin:
    def dispatch(self, request, *args, **kwargs):
        # validate year
        try:
            year = int(kwargs["year"])
            if year < 1 or year > 9999:
                raise ValueError()
        except ValueError:
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    @property
    def year(self):
        return self.kwargs["year"]

    def get_context_data(self, **kwargs):
        return super().get_context_data(year=self.year, **kwargs)


class YearListMixin(YearMixin):
    def page_title(self):
        return f"{super().page_title()} - {self.year}"

    def get_base_queryset(self, exclude=None):
        qs = super().get_base_queryset()
        if exclude is None:
            exclude = []
        if "year" not in exclude:
            qs = qs.filter(date__year=self.kwargs["year"])
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.populate_months(context)
        return context

    def populate_months(self, context):
        context["months"] = self.get_base_queryset(exclude=["month"]).dates(
            "date", "month", order="ASC"
        )
