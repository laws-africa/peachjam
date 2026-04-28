import operator
from collections import defaultdict
from functools import reduce

from django.conf import settings
from django.contrib import messages
from django.db.models import F, IntegerField, Q, Value, Window
from django.db.models.functions import Coalesce, Length, RowNumber, Substr
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.text import gettext_lazy as _
from django.utils.timezone import now
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView, ListView, TemplateView

from peachjam.helpers import add_slash_to_frbr_uri
from peachjam.models import CourtClass, Judgment
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
            settings.PEACHJAM.get("SUMMARISE_USE_FLYNOTE_TREE", False)
            and Flynote.get_root_nodes().exists()
        )
        self.add_entity_profile(context)
        self.get_court_classes(context)
        return context

    def get_court_classes(self, context):
        context["court_classes"] = CourtClass.objects.prefetch_related("courts")

    def add_entity_profile(self, context):
        pass


class FlynoteViewMixin:
    @staticmethod
    def flynote_topics_enabled():
        return settings.PEACHJAM.get("SUMMARISE_USE_FLYNOTE_TREE", False)

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
            Flynote.objects.filter(depth=depth + 1)
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
            }
            for f in flynotes
        ]


class FlynoteListView(FlynoteViewMixin, ListView):
    """Lists flynotes. By default, it lists popular top-level flynotes. With htmx, it lists paginated top-level
    flynotes, or subtopics if a root flynote is given.
    """

    model = Flynote
    template_name = "peachjam/flynote/list.html"
    context_object_name = "flynotes"
    paginate_by = 30

    def get(self, request, *args, **kwargs):
        if not self.flynote_topics_enabled() or not Flynote.get_root_nodes().exists():
            return redirect(reverse("judgment_list"))
        return super().get(request, *args, **kwargs)

    def get_template_names(self):
        if self.request.htmx:
            return ["peachjam/flynote/_list.html"]
        return super().get_template_names()

    @cached_property
    def flynote(self):
        """In htmx mode, the ?flynote=<pk> parameter anchors the list of subtopics."""
        if self.request.GET.get("flynote"):
            return get_object_or_404(Flynote, pk=self.request.GET.get("flynote"))

    def get_queryset(self):
        if self.flynote:
            # children of the provided root
            qs = self.flynote.get_children()
        else:
            # all roots
            qs = Flynote.get_root_nodes()

        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(name__icontains=q)

        return self.annotate_with_counts(qs).order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["flynotes"] = self.make_flynote_list(list(context["flynotes"]))
        # ensure that the template appends, rather than replaces, when "load more" is clicked
        context["more"] = "more" in self.request.GET

        if not self.request.htmx:
            # for non-htmx, load popular flynotes
            self.popular_flynotes(context)

        return context

    def popular_flynotes(self, context):
        qs = self.annotate_with_counts(Flynote.get_root_nodes()).order_by(
            "-doc_count", "name"
        )[:16]
        context["popular_flynotes"] = self.make_flynote_list(list(qs))


class FlynoteDetailView(FlynoteViewMixin, FilteredDocumentListView):
    """List of documents and children under a flynote. In HTMX mode, updates the document list."""

    template_name = "peachjam/flynote/detail.html"
    navbar_link = "judgments"

    def get_template_names(self):
        if self.request.htmx:
            return ["peachjam/_document_table.html"]
        return super().get_template_names()

    def dispatch(self, request, *args, **kwargs):
        if not self.flynote_topics_enabled():
            return redirect(reverse("judgment_list"))
        self.flynote = get_object_or_404(Flynote, slug=self.kwargs["slug"])
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

        if not self.request.htmx:
            self.popular_subtopics(context)
            context["flynote"] = self.flynote
            context["ancestors"] = self.flynote.get_ancestors()

        return context

    def popular_subtopics(self, context):
        # Top 16 subtopcis by count
        children_qs = self.annotate_with_counts(self.flynote.get_children())
        total_children = children_qs.count()
        popular_flynotes = list(children_qs.order_by("-doc_count", "name")[:16])

        context["popular_flynotes"] = self.make_flynote_list(popular_flynotes)
        context["has_more_topics"] = total_children > len(popular_flynotes)
        context["total_subtopic_count"] = total_children


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
@method_decorator(never_cache, name="dispatch")
class CaseHistoryView(SubscriptionRequiredMixin, DetailView):
    permission_required = "peachjam.can_view_case_history"
    model = Judgment
    slug_url_kwarg = "frbr_uri"
    slug_field = "expression_frbr_uri"
    template_name = "peachjam/_case_histories.html"

    def get_subscription_required_template(self):
        return self.template_name

    def add_case_histories(self, context):
        document = self.get_object()

        # judgments that impact this one
        histories = [
            {
                "document": ch.judgment_work.documents.first(),
                "children": [
                    {
                        "case_history": ch,
                        "document": document,
                    }
                ],
            }
            for ch in document.work.incoming_case_histories.select_related(
                "court", "historical_judgment_work", "outcome"
            )
            # ignore incoming history entries for dangling works that don't have a document
            if ch.judgment_work.documents.first()
        ]

        if histories:
            context["show_review_notice"] = True

        # judgments that this one impacts
        outgoing_histories = [
            {
                "case_history": ch,
                "document": (
                    ch.historical_judgment_work.documents.first()
                    if ch.historical_judgment_work
                    else None
                ),
            }
            for ch in document.work.case_histories.select_related(
                "historical_judgment_work", "outcome"
            ).prefetch_related(
                "historical_judgment_work__documents",
                "historical_judgment_work__documents__outcomes",
                "historical_judgment_work__documents__court",
                "historical_judgment_work__documents__judges",
            )
        ]
        if outgoing_histories:
            histories.append(
                {
                    "document": document,
                    "children": outgoing_histories,
                }
            )

        today = now().date()
        for history in histories:
            for child in history["children"]:
                child["info"] = child["document"] or child["case_history"]

            # sort by date descending
            history["children"].sort(
                key=lambda x: x["info"].date or today, reverse=True
            )

        # sort by date descending
        histories.sort(key=lambda x: x["document"].date, reverse=True)

        context["case_histories"] = histories

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
@method_decorator(never_cache, name="dispatch")
class CaseSummaryView(SubscriptionRequiredMixin, DetailView):
    permission_required = "peachjam.can_view_document_summary"
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
