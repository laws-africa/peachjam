import operator
from collections import defaultdict
from functools import reduce

from django.contrib import messages
from django.db.models import F, IntegerField, Q, Value, Window
from django.db.models.functions import Coalesce, Length, RowNumber, Substr
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.cache import add_never_cache_headers
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.text import gettext_lazy as _
from django.views.generic import DetailView, ListView, TemplateView

from peachjam.forms import FlynoteDocumentFilterForm
from peachjam.helpers import add_slash_to_frbr_uri
from peachjam.models import CaseHistory, CourtClass, Judgment
from peachjam.models.flynote import Flynote
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)
from peachjam_subs.mixins import SubscriptionRequiredMixin


class JudgmentListView(TemplateView):
    template_name = "peachjam/judgment_list.html"
    navbar_link = "judgments"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["recent_judgments"] = (
            Judgment.objects.for_document_table()
            .exclude(published=False)
            .order_by("-date")[:30]
        )
        context["nature"] = "Judgment"
        context["doc_count"] = Judgment.objects.filter(published=True).count()
        context["doc_count_noun"] = _("judgment")
        context["doc_count_noun_plural"] = _("judgments")
        context["help_link"] = "judgments/courts"
        context["show_flynote_topics"] = (
            Judgment.flynote_topics_enabled()
            and Flynote.objects.undeprecated().filter(depth=1).exists()
        )
        self.add_entity_profile(context)
        self.get_court_classes(context)
        return context

    def get_court_classes(self, context):
        context["court_classes"] = CourtClass.objects.prefetch_related("courts")

    def add_entity_profile(self, context):
        pass


class FlynoteViewMixin:
    matching_subtopics_per_card = 3

    @staticmethod
    def flynote_tree_enabled():
        return Judgment.flynote_tree_enabled()

    @staticmethod
    def flynote_topics_enabled():
        return Judgment.flynote_topics_enabled()

    @staticmethod
    def annotate_with_counts(qs):
        return qs.annotate(
            doc_count=Coalesce(
                F("document_count_cache__count"),
                Value(0),
                output_field=IntegerField(),
            )
        )

    @staticmethod
    def get_top_children_by_count(parent_flynotes):
        if not parent_flynotes:
            return {}

        depth = parent_flynotes[0].depth
        direct_child_filter = reduce(
            operator.or_,
            (Q(path__startswith=flynote.path) for flynote in parent_flynotes),
        )

        children_qs = (
            Flynote.objects.undeprecated()
            .filter(depth=depth + 1)
            .filter(direct_child_filter)
            .annotate(
                parent_path=Substr("path", 1, Length("path") - Flynote.steplen),
                doc_count=Coalesce(
                    F("document_count_cache__count"),
                    Value(0),
                    output_field=IntegerField(),
                ),
            )
            .annotate(
                rank=Window(
                    expression=RowNumber(),
                    partition_by=[F("parent_path")],
                    order_by=[F("doc_count").desc(), F("name").asc()],
                ),
            )
            .filter(rank__lte=3)
            .order_by("parent_path", "rank")
        )

        children_by_parent = defaultdict(list)
        for child in children_qs:
            children_by_parent[child.parent_path].append(child.name)

        path_to_pk = {f.path: f.pk for f in parent_flynotes}
        return {path_to_pk[path]: names for path, names in children_by_parent.items()}

    def make_flynote_list(self, flynotes):
        child_names = self.get_top_children_by_count(flynotes)
        return [
            {
                "flynote": f,
                "count": f.doc_count,
                "child_names": child_names.get(f.pk, []),
                "more_child_count": max(0, f.numchild - len(child_names.get(f.pk, []))),
            }
            for f in flynotes
        ]

    def filter_flynote_descendants_by_query(self, children_qs, query, parent_path):
        """Filter direct children by matching descendants and collect the matching paths."""
        matching_flynotes = list(
            self.annotate_with_counts(
                Flynote.objects.undeprecated().filter(
                    path__startswith=parent_path,
                    name__icontains=query,
                )
            )
            .exclude(path=parent_path)
            .only("pk", "path", "name", "depth")
        )
        child_path_length = len(parent_path) + Flynote.steplen
        matching_child_paths = {
            flynote.path[:child_path_length] for flynote in matching_flynotes
        }
        children_qs = children_qs.filter(path__in=matching_child_paths)
        visible_child_paths = set(children_qs.values_list("path", flat=True))

        matching_flynotes_by_child = defaultdict(list)
        for flynote in matching_flynotes:
            child_path = flynote.path[:child_path_length]
            if child_path not in visible_child_paths or flynote.path == child_path:
                continue
            matching_flynotes_by_child[child_path].append(flynote)

        requested_paths = set()
        matching_paths = defaultdict(list)
        matching_more_counts = {}
        for child_path, child_matches in matching_flynotes_by_child.items():
            child_matches.sort(
                key=lambda flynote: (
                    flynote.depth,
                    -flynote.doc_count,
                    flynote.name.casefold(),
                )
            )
            matching_more_counts[child_path] = max(
                0, len(child_matches) - self.matching_subtopics_per_card
            )
            for flynote in child_matches[: self.matching_subtopics_per_card]:
                path = [
                    flynote.path[:end]
                    for end in range(
                        child_path_length + Flynote.steplen,
                        len(flynote.path) + 1,
                        Flynote.steplen,
                    )
                ]
                requested_paths.update(path)
                matching_paths[child_path].append(path)

        flynotes_by_path = {
            flynote.path: flynote
            for flynote in Flynote.objects.undeprecated()
            .filter(path__in=requested_paths)
            .order_by("path")
        }
        return (
            children_qs,
            {
                child_path: [
                    {"nodes": [flynotes_by_path[path] for path in path_group]}
                    for path_group in path_groups
                ]
                for child_path, path_groups in matching_paths.items()
            },
            matching_more_counts,
        )


class FlynoteListView(FlynoteViewMixin, ListView):
    """Lists top-level flynotes for exploration."""

    model = Flynote
    template_name = "peachjam/flynote/list.html"
    context_object_name = "flynotes"
    paginate_by = None

    def get(self, request, *args, **kwargs):
        if (
            not self.flynote_tree_enabled()
            or not Flynote.objects.undeprecated().filter(depth=1).exists()
        ):
            return redirect(reverse("judgment_list"))
        return super().get(request, *args, **kwargs)

    def get_template_names(self):
        if self.request.htmx:
            return ["peachjam/flynote/_topic_results.html"]
        return super().get_template_names()

    def get_queryset(self):
        return self.annotate_with_counts(
            Flynote.objects.undeprecated().filter(depth=1)
        ).filter(doc_count__gt=0)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        topics_qs = context["flynotes"]
        query = self.request.GET.get("q", "").strip()
        sort = self.request.GET.get("sort", "judgments")
        if query:
            (
                topics_qs,
                matching_paths,
                matching_more_counts,
            ) = self.filter_flynote_descendants_by_query(topics_qs, query, "")
        else:
            matching_paths = {}
            matching_more_counts = {}

        ordering = ("name",) if sort == "name" else ("-doc_count", "name")
        topic_items = self.make_flynote_list(list(topics_qs.order_by(*ordering)))
        for item in topic_items:
            item["matching_paths"] = matching_paths.get(item["flynote"].path, [])
            item["matching_more_count"] = matching_more_counts.get(
                item["flynote"].path, 0
            )
            item["inline_child_names"] = True
        context["flynotes"] = topic_items
        context["flynote_cards"] = topic_items
        context["topic_count"] = len(topic_items)
        context["topic_query"] = query
        context["flynote_query"] = query
        context["topic_sort"] = sort
        return context


class FlynoteDetailView(
    SubscriptionRequiredMixin, FlynoteViewMixin, FilteredDocumentListView
):
    """List of documents and children under a flynote. In HTMX mode, updates the document list."""

    form_class = FlynoteDocumentFilterForm
    form_defaults = {
        "sort": FlynoteDocumentFilterForm.most_cited_sort,
        "secondary_sort": "-date",
    }
    template_name = "peachjam/flynote/detail.html"
    navbar_link = "judgments"
    permission_required = "peachjam.view_linked_judgments"
    initial_subtopics_page_size = 9
    more_subtopics_page_size = 15
    search_subtopics_page_size = 12

    def get_flynote_document_listing_id(self):
        return f"flynote-document-listing-{self.flynote.pk}"

    def is_linked_judgments_htmx_request(self):
        return self.request.htmx and self.request.htmx.target in {
            self.get_flynote_document_listing_id(),
            self.get_document_table_form_id(),
            self.get_document_table_id(),
        }

    def is_subtopics_htmx_request(self):
        return (
            self.request.htmx and self.request.htmx.target == "flynote-more-subtopics"
        )

    def is_subtopics_search_htmx_request(self):
        return (
            self.request.htmx and self.request.htmx.target == "flynote-subtopic-results"
        )

    def has_permission(self):
        if not self.is_linked_judgments_htmx_request():
            return True
        return super().has_permission()

    def get_template_names(self):
        if self.is_subtopics_htmx_request():
            return ["peachjam/flynote/_more_cards.html"]
        if self.is_subtopics_search_htmx_request():
            return ["peachjam/flynote/_cards_results.html"]
        if (
            self.request.htmx
            and self.request.htmx.target == self.get_flynote_document_listing_id()
        ):
            return ["peachjam/_document_table_form.html"]
        return super().get_template_names()

    def dispatch(self, request, *args, **kwargs):
        if not self.flynote_tree_enabled():
            return redirect(reverse("judgment_list"))
        self.flynote = get_object_or_404(
            Flynote.objects.undeprecated(), pk=self.kwargs["pk"]
        )
        return super().dispatch(request, *args, **kwargs)

    def get_base_queryset(self):
        return (
            super()
            .get_base_queryset()
            .filter(
                judgment__flynotes__flynote__path__startswith=self.flynote.path,
            )
            .distinct()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["doc_table_show_doc_type"] = False
        context["doc_table_show_jurisdiction"] = False
        context["flynote_document_listing_id"] = self.get_flynote_document_listing_id()

        if (
            not self.request.htmx
            or self.is_subtopics_htmx_request()
            or self.is_subtopics_search_htmx_request()
        ):
            self.subtopic_cards(context)
            context["flynote"] = self.flynote
            context["ancestors"] = self.flynote.get_ancestors()

        return context

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        if self.request.htmx:
            add_never_cache_headers(response)
        return response

    def subtopic_cards(self, context):
        children_qs = self.annotate_with_counts(
            self.flynote.get_children().filter(deprecated=False)
        ).filter(doc_count__gt=0)
        query = self.request.GET.get("subtopic_q", "").strip()
        sort = self.request.GET.get("sort", "judgments")
        subtopics_offset = 0
        if self.is_subtopics_htmx_request():
            try:
                subtopics_offset = max(
                    0, int(self.request.GET.get("subtopics_offset", 0))
                )
            except (TypeError, ValueError):
                pass

        if query:
            (
                children_qs,
                matching_paths,
                matching_more_counts,
            ) = self.filter_flynote_descendants_by_query(
                children_qs, query, self.flynote.path
            )
            page_size = self.search_subtopics_page_size
        else:
            matching_paths = {}
            matching_more_counts = {}
            page_size = (
                self.more_subtopics_page_size
                if self.is_subtopics_htmx_request()
                else self.initial_subtopics_page_size
            )

        ordering = ("name",) if sort == "name" else ("-doc_count", "name")
        total_subtopic_count = children_qs.count()
        flynote_cards = list(
            children_qs.order_by(*ordering)[
                subtopics_offset : subtopics_offset + page_size
            ]
        )
        next_subtopics_offset = subtopics_offset + len(flynote_cards)

        context["flynote_cards"] = self.make_flynote_list(flynote_cards)
        for item in context["flynote_cards"]:
            item["matching_paths"] = matching_paths.get(item["flynote"].path, [])
            item["matching_more_count"] = matching_more_counts.get(
                item["flynote"].path, 0
            )
        context["has_more_topics"] = next_subtopics_offset < total_subtopic_count
        context["next_subtopics_offset"] = (
            next_subtopics_offset if context["has_more_topics"] else None
        )
        context["total_subtopic_count"] = total_subtopic_count
        context["subtopic_query"] = query
        context["flynote_query"] = query
        context["subtopic_sort"] = sort


@registry.register_doc_type("judgment")
class JudgmentDetailView(BaseDocumentDetailView):
    model = Judgment
    template_name = "peachjam/judgment_detail.html"

    def get_notices(self):
        notices = super().get_notices()
        document = self.get_object()
        if document.anonymised:
            notices.append(
                {
                    "type": messages.INFO,
                    "html": mark_safe(
                        _(
                            "This judgment has been anonymised to protect personal "
                            "information in compliance with the law."
                        )
                    ),
                }
            )
        return notices

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["judges"] = [
            bench.judge
            for bench in self.get_object().bench.select_related("judge").all()
        ]
        return context


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class CaseHistoryView(SubscriptionRequiredMixin, DetailView):
    permission_required = "peachjam.can_view_case_history"
    private_cache = True
    model = Judgment
    slug_url_kwarg = "frbr_uri"
    slug_field = "expression_frbr_uri"
    template_name = "peachjam/_case_histories.html"

    def get_subscription_required_template(self):
        return self.template_name

    def add_case_histories(self, context):
        document = self.get_object()
        case_histories = self.get_connected_case_histories(document.work_id)
        histories = self.get_case_history_entries(document, case_histories)

        context["show_review_notice"] = bool(case_histories)

        context["case_histories"] = histories
        return histories

    def get_connected_case_histories(self, root_work_id):
        case_histories = {}
        pending_work_ids = {root_work_id}
        visited_work_ids = set()

        while pending_work_ids:
            work_ids_to_process = pending_work_ids
            pending_work_ids = set()
            visited_work_ids.update(work_ids_to_process)

            histories = CaseHistory.objects.filter(
                Q(judgment_work_id__in=work_ids_to_process)
                | Q(historical_judgment_work_id__in=work_ids_to_process)
            )

            for case_history in histories:
                if case_history.pk in case_histories:
                    continue

                case_histories[case_history.pk] = case_history
                for work_id in (
                    case_history.judgment_work_id,
                    case_history.historical_judgment_work_id,
                ):
                    if work_id and work_id not in visited_work_ids:
                        pending_work_ids.add(work_id)

        return list(case_histories.values())

    def get_case_history_entries(self, document, case_histories):
        work_ids = {document.work_id}
        for case_history in case_histories:
            work_ids.add(case_history.judgment_work_id)
            if case_history.historical_judgment_work_id:
                work_ids.add(case_history.historical_judgment_work_id)

        documents_by_work_id = {document.work_id: document}
        related_documents = (
            Judgment.objects.filter(work_id__in=work_ids - {document.work_id})
            .latest_expression()
            .select_related("court")
            .prefetch_related("judges", "outcomes")
        )
        for related_document in related_documents:
            documents_by_work_id[related_document.work_id] = related_document

        histories = []
        for case_document in documents_by_work_id.values():
            history = {
                "document": case_document,
                "is_current": case_document.work_id == document.work_id,
            }
            histories.append(history)

        histories.sort(key=lambda history: history["document"].date, reverse=True)

        return histories

    def get_subscription_required_context(self):
        context = {}
        self.add_case_histories(context)
        return context

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_subscription_required_context())
        return context


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class CaseSummaryView(SubscriptionRequiredMixin, DetailView):
    permission_required = "peachjam.can_view_document_summary"
    private_cache = True
    template_name = "peachjam/document/_judgment_summary.html"
    model = Judgment
    slug_url_kwarg = "frbr_uri"
    slug_field = "expression_frbr_uri"

    def has_permission(self):
        document = self.get_object()
        is_public = document.case_summary_public
        if is_public:
            return True
        return super().has_permission()

    def get_subscription_required_template(self):
        return self.template_name

    def get_subscription_required_context(self):
        context = {}
        document = self.get_object()
        if hasattr(document, "case_summary"):
            context = {"document": document}
        return context

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_subscription_required_context())
        return context
