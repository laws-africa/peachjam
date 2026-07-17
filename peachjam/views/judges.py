from functools import cached_property
from statistics import median
from urllib.parse import urlencode

from django.contrib import admin, messages
from django.contrib.admin.utils import quote
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Exists, Max, Min, OuterRef, Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.utils.translation import gettext_lazy
from django.views.generic import ListView, TemplateView

from peachjam.analysis.judges import judge_identity_service
from peachjam.forms import JudgeIdentityWorkflowForm
from peachjam.models import (
    Bench,
    ExtractedCitation,
    Flynote,
    Judge,
    JudgeAlias,
    JudgePerson,
    Judgment,
    JudgmentFlynote,
)
from peachjam.views.courts import FilteredJudgmentView


def available_judge_flynote_topics(judge_person=None):
    """Return top-level flynote topics linked to canonical judges' judgments."""
    if not Judgment.flynote_topics_enabled():
        return Flynote.objects.none()

    linked_judgments = JudgmentFlynote.objects.filter(
        flynote__path__startswith=OuterRef("path"),
        document__published=True,
        document__bench__judge_person__isnull=False,
    )
    if judge_person is not None:
        linked_judgments = linked_judgments.filter(
            document__bench__judge_person=judge_person
        )

    return (
        Flynote.get_root_nodes()
        .filter(deprecated=False)
        .annotate(has_judge_judgments=Exists(linked_judgments))
        .filter(has_judge_judgments=True)
        .order_by("name")
    )


def group_years_into_ranges(years):
    """Group available years into descending decade ranges for compact filters."""
    years = sorted({int(year) for year in years if year is not None}, reverse=True)
    if not years:
        return []

    latest_year = years[0]
    years_by_decade = {}
    for year in years:
        decade = year // 10 * 10
        years_by_decade.setdefault(decade, []).append(year)

    return [
        {
            "label": f"{decade}–{min(decade + 9, latest_year)}",
            "start": decade,
            "end": min(decade + 9, latest_year),
            "years": years_by_decade[decade],
        }
        for decade in sorted(years_by_decade, reverse=True)
    ]


def percentage_chart_rows(rows, count_key="judgment_count"):
    """Add relative percentages to count rows for server-rendered bar charts."""
    rows = list(rows)
    maximum = max((row[count_key] for row in rows), default=0)
    for row in rows:
        row["percentage"] = (
            max(round(row[count_key] / maximum * 100), 3) if maximum else 0
        )
    return rows


JUDGE_SURNAME_PARTICLES = {
    "da",
    "de",
    "del",
    "der",
    "di",
    "du",
    "la",
    "le",
    "van",
    "von",
}


def split_judge_display_name(name):
    """Split a surname-first full name while preserving the complete display name."""
    name = " ".join((name or "").split())
    if not name:
        return "", ""

    if "," in name:
        surname, remainder = name.split(",", 1)
        remainder = remainder.strip()
        return surname.strip(), f", {remainder}" if remainder else ","

    parts = name.split()
    surname_end = 1
    while (
        surname_end < len(parts) - 1
        and parts[surname_end - 1].rstrip(".").casefold() in JUDGE_SURNAME_PARTICLES
    ):
        surname_end += 1

    surname = " ".join(parts[:surname_end])
    remainder = " ".join(parts[surname_end:])
    return surname, f" {remainder}" if remainder else ""


class JudgePublicPageMixin:
    def dispatch(self, request, *args, **kwargs):
        if not JudgePerson.canonical_identity_public_enabled():
            raise Http404("Canonical judge identity public pages are disabled.")
        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def available_flynote_topics(self):
        return list(available_judge_flynote_topics(self.get_topic_judge_person()))

    def get_topic_judge_person(self):
        return None

    @cached_property
    def selected_flynote_topics(self):
        topic_ids = self.request.GET.getlist("topics")
        selected_ids = {int(value) for value in topic_ids if value.isdigit()}
        return [
            topic for topic in self.available_flynote_topics if topic.pk in selected_ids
        ]

    def selected_courts(self):
        return self.request.GET.getlist("courts")

    def selected_years(self):
        years = set()
        for value in self.request.GET.getlist("year_ranges"):
            try:
                start, end = (int(part) for part in value.split(":", 1))
            except (TypeError, ValueError):
                continue
            if 1000 <= start <= end <= 9999 and end - start <= 9:
                years.update(range(start, end + 1))
        return sorted(years)

    def topic_filter_context(self):
        return [
            {
                "label": topic.name,
                "value": topic.pk,
                "selected": topic in self.selected_flynote_topics,
            }
            for topic in self.available_flynote_topics
        ]

    def year_filter_context(self, years, selected_years=None):
        selected_years = (
            self.selected_years() if selected_years is None else selected_years
        )
        selected_year_values = {
            int(value) for value in selected_years if str(value).isdigit()
        }
        return [
            {
                **year_range,
                "value": f"{year_range['start']}:{year_range['end']}",
                "selected": set(year_range["years"]).issubset(selected_year_values),
            }
            for year_range in group_years_into_ranges(years)
        ]


class JudgePersonListView(JudgePublicPageMixin, ListView):
    template_name = "peachjam/judge_list.html"
    context_object_name = "judges"
    navbar_link = "judgments"
    # Keep the directory manageable while preserving alphabetical grouping within
    # each page. Filter query parameters are retained by the shared paginator.
    paginate_by = 10

    def get_base_queryset(self):
        return (
            JudgePerson.objects.filter(bench_entries__isnull=False)
            .annotate(
                judgment_count=Count(
                    "bench_entries__judgment",
                    filter=Q(bench_entries__judgment__published=True),
                    distinct=True,
                ),
                first_year=Min(
                    "bench_entries__judgment__date__year",
                    filter=Q(bench_entries__judgment__published=True),
                ),
                latest_year=Max(
                    "bench_entries__judgment__date__year",
                    filter=Q(bench_entries__judgment__published=True),
                ),
            )
            .distinct()
        )

    def get_queryset(self):
        queryset = self.get_base_queryset()

        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(full_name__icontains=q)

        selected_courts = self.selected_courts()
        if selected_courts:
            judge_ids = Bench.objects.filter(
                judgment__published=True,
                judgment__court__name__in=selected_courts,
                judge_person__isnull=False,
            ).values_list("judge_person_id", flat=True)
            queryset = queryset.filter(pk__in=judge_ids)

        if self.selected_flynote_topics:
            topic_query = Q()
            for topic in self.selected_flynote_topics:
                topic_query |= Q(
                    judgment__flynotes__flynote__path__startswith=topic.path
                )
            judge_ids = Bench.objects.filter(
                topic_query,
                judgment__published=True,
                judge_person__isnull=False,
            ).values_list("judge_person_id", flat=True)
            queryset = queryset.filter(pk__in=judge_ids)

        selected_years = set(self.selected_years())
        if selected_years:
            judge_ids = Bench.objects.filter(
                judgment__published=True,
                judgment__date__year__in=selected_years,
                judge_person__isnull=False,
            ).values_list("judge_person_id", flat=True)
            queryset = queryset.filter(pk__in=judge_ids)

        # Default to A-Z for the address-book layout; "judgments" is an explicit opt-in.
        if self.request.GET.get("sort") == "judgments":
            return queryset.order_by("-judgment_count", "full_name", "pk")
        if self.request.GET.get("sort") == "name_desc":
            return queryset.order_by("-full_name", "-pk")
        return queryset.order_by("full_name", "pk")

    def add_judge_metadata(self, judges):
        judge_ids = [judge.pk for judge in judges]
        courts_by_judge = {judge_id: [] for judge_id in judge_ids}

        for judge_id, court_name in (
            Bench.objects.filter(
                judge_person_id__in=judge_ids,
                judgment__published=True,
            )
            .values_list("judge_person_id", "judgment__court__name")
            .order_by("judgment__court__name")
            .distinct()
        ):
            if court_name:
                courts_by_judge[judge_id].append(court_name)

        for judge in judges:
            court_names = courts_by_judge.get(judge.pk, [])
            judge.court_names = court_names[:3]
            judge.more_courts_count = max(len(court_names) - len(judge.court_names), 0)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        judges = list(context["judges"])
        self.add_judge_metadata(judges)

        for judge in judges:
            first_letter = judge.full_name[0].upper() if judge.full_name else "#"
            judge.first_letter = first_letter
            judge.display_surname, judge.display_name_remainder = (
                split_judge_display_name(judge.full_name)
            )

        if self.request.GET.get("sort") == "judgments":
            context["grouped_judges"] = [(None, judges)]
        else:
            grouped = {}
            for judge in judges:
                grouped.setdefault(judge.first_letter, []).append(judge)
            context["grouped_judges"] = [
                (letter, grouped[letter])
                for letter in sorted(
                    grouped,
                    reverse=self.request.GET.get("sort") == "name_desc",
                )
            ]

        context["judges"] = judges
        context["q"] = self.request.GET.get("q", "").strip()
        context["sort"] = self.request.GET.get("sort", "name")
        context["selected_judge_courts"] = self.selected_courts()
        context["selected_flynote_topics"] = self.selected_flynote_topics
        context["selected_judge_years"] = [str(year) for year in self.selected_years()]
        context["judge_count"] = context["paginator"].count
        available_courts = list(
            Bench.objects.filter(
                judgment__published=True,
                judge_person__isnull=False,
            )
            .values_list("judgment__court__name", flat=True)
            .exclude(judgment__court__name__isnull=True)
            .exclude(judgment__court__name="")
            .distinct()
            .order_by("judgment__court__name")
        )
        context["judge_court_filters"] = [
            {
                "label": court,
                "value": court,
                "selected": court in context["selected_judge_courts"],
            }
            for court in available_courts
        ]
        available_years = list(
            Bench.objects.filter(
                judge_person__isnull=False,
                judgment__published=True,
                judgment__date__isnull=False,
            )
            .values_list("judgment__date__year", flat=True)
            .distinct()
            .order_by("-judgment__date__year")
        )
        context["judge_year_filters"] = self.year_filter_context(
            available_years,
            selected_years=context["selected_judge_years"],
        )
        context["judge_topic_filters"] = self.topic_filter_context()
        return context


class JudgePersonDetailView(JudgePublicPageMixin, FilteredJudgmentView):
    template_name = "peachjam/judge_detail.html"
    document_table_form_template_name = (
        "peachjam/_judge_detail_document_table_form.html"
    )
    navbar_link = "judgments"

    @cached_property
    def judge_person(self):
        return get_object_or_404(JudgePerson, slug=self.kwargs["slug"])

    def base_view_name(self):
        return self.judge_person.full_name

    def get_topic_judge_person(self):
        return self.judge_person

    def get_base_queryset(self, exclude=None):
        queryset = (
            super()
            .get_base_queryset(exclude=exclude)
            .filter(bench__judge_person=self.judge_person)
        )
        if self.selected_flynote_topics:
            topic_query = Q()
            for topic in self.selected_flynote_topics:
                topic_query |= Q(flynotes__flynote__path__startswith=topic.path)
            queryset = queryset.filter(topic_query)
        if self.selected_years():
            queryset = queryset.filter(date__year__in=self.selected_years())
        return queryset

    def add_facets(self, context):
        # Judge pages use focused court, year, and topic filters instead of the
        # generic document sidebar, whose alphabet filter is not useful here.
        context["facet_data"] = {}

    def get_citation_analysis(self, bench_entries):
        """Build citation influence data from the judge's linked judgment works."""
        work_ids = bench_entries.values_list("judgment__work_id", flat=True).distinct()
        if not work_ids.exists():
            return {
                "incoming_count": 0,
                "outgoing_count": 0,
                "citing_judges": [],
                "cited_judges": [],
                "most_cited_judgments": [],
            }

        incoming_citations = ExtractedCitation.objects.filter(
            target_work_id__in=work_ids,
            citing_work__documents__published=True,
        ).exclude(citing_work_id__in=work_ids)
        outgoing_citations = ExtractedCitation.objects.filter(
            citing_work_id__in=work_ids,
            target_work__documents__published=True,
        ).exclude(target_work_id__in=work_ids)
        incoming_work_ids = incoming_citations.values_list(
            "citing_work_id", flat=True
        ).distinct()
        outgoing_work_ids = outgoing_citations.values_list(
            "target_work_id", flat=True
        ).distinct()

        connection_fields = ("judge_person__full_name", "judge_person__slug")
        citing_judges = list(
            Bench.objects.filter(
                judgment__work_id__in=incoming_work_ids,
                judgment__published=True,
                judge_person__isnull=False,
            )
            .exclude(judge_person=self.judge_person)
            .values(*connection_fields)
            .annotate(judgment_count=Count("judgment__work_id", distinct=True))
            .order_by("-judgment_count", "judge_person__full_name")[:5]
        )
        cited_judges = list(
            Bench.objects.filter(
                judgment__work_id__in=outgoing_work_ids,
                judgment__published=True,
                judge_person__isnull=False,
            )
            .exclude(judge_person=self.judge_person)
            .values(*connection_fields)
            .annotate(judgment_count=Count("judgment__work_id", distinct=True))
            .order_by("-judgment_count", "judge_person__full_name")[:5]
        )
        most_cited_judgments = list(
            Judgment.objects.filter(bench__judge_person=self.judge_person)
            .filter(published=True)
            .annotate(
                incoming_citation_count=Count(
                    "work__incoming_citations__citing_work",
                    filter=(
                        ~Q(work__incoming_citations__citing_work_id__in=work_ids)
                        & Q(
                            work__incoming_citations__citing_work__documents__published=True
                        )
                    ),
                    distinct=True,
                )
            )
            .filter(incoming_citation_count__gt=0)
            .order_by("-incoming_citation_count", "-date", "title")[:5]
        )
        return {
            "incoming_count": incoming_work_ids.count(),
            "outgoing_count": outgoing_work_ids.count(),
            "citing_judges": citing_judges,
            "cited_judges": cited_judges,
            "most_cited_judgments": most_cited_judgments,
        }

    def get_topic_chart(self):
        topic_counts = {topic.pk: set() for topic in self.available_flynote_topics}
        topic_names = {topic.pk: topic.name for topic in self.available_flynote_topics}
        topic_paths = {topic.pk: topic.path for topic in self.available_flynote_topics}

        rows = (
            JudgmentFlynote.objects.filter(
                document__bench__judge_person=self.judge_person,
                document__published=True,
            )
            .values("document_id", "flynote__path")
            .distinct()
        )
        for row in rows:
            flynote_path = row["flynote__path"]
            for topic_id, topic_path in topic_paths.items():
                if flynote_path.startswith(topic_path):
                    topic_counts[topic_id].add(row["document_id"])

        topic_rows = [
            {
                "name": topic_names[topic_id],
                "judgment_count": len(document_ids),
            }
            for topic_id, document_ids in topic_counts.items()
            if document_ids
        ]
        topic_rows.sort(key=lambda row: (-row["judgment_count"], row["name"]))
        return percentage_chart_rows(topic_rows[:8])

    def get_primary_court_context(self, primary_court):
        context = {
            "judge_primary_court": primary_court,
            "judge_primary_court_comparison": [],
        }
        if not primary_court:
            return context

        peer_counts = list(
            Bench.objects.filter(
                judgment__court__name=primary_court["judgment__court__name"],
                judgment__published=True,
                judge_person__isnull=False,
            )
            .values("judge_person_id")
            .annotate(judgment_count=Count("judgment_id", distinct=True))
            .values_list("judgment_count", flat=True)
        )
        if peer_counts:
            primary_court_median = round(float(median(peer_counts)), 1)
            context["judge_primary_court_comparison"] = percentage_chart_rows(
                [
                    {
                        "label": gettext_lazy("This judge"),
                        "judgment_count": primary_court["judgment_count"],
                    },
                    {
                        "label": gettext_lazy("Court median"),
                        "judgment_count": primary_court_median,
                    },
                ]
            )
        return context

    def get_filter_context(self, judge_court_breakdown, judge_year_breakdown):
        selected_courts = self.selected_courts()
        selected_years = [str(year) for year in self.selected_years()]
        return {
            "selected_judge_courts": selected_courts,
            "selected_judge_years": selected_years,
            "selected_flynote_topics": self.selected_flynote_topics,
            "judge_court_filters": [
                {
                    "label": row["judgment__court__name"],
                    "value": row["judgment__court__name"],
                    "selected": row["judgment__court__name"] in selected_courts,
                }
                for row in judge_court_breakdown
            ],
            "judge_year_filters": self.year_filter_context(
                (row["judgment__date__year"] for row in judge_year_breakdown),
                selected_years=selected_years,
            ),
            "judge_topic_filters": self.topic_filter_context(),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["judge_person"] = self.judge_person
        context["doc_table_show_court"] = True
        bench_entries = Bench.objects.filter(
            judge_person=self.judge_person,
            judgment__published=True,
        )
        judge_court_breakdown = list(
            bench_entries.exclude(judgment__court__name__isnull=True)
            .exclude(judgment__court__name="")
            .values("judgment__court__name")
            .annotate(
                judgment_count=Count("judgment", distinct=True),
                first_year=Min("judgment__date__year"),
                latest_year=Max("judgment__date__year"),
            )
            .order_by("-judgment_count", "judgment__court__name")
        )
        judge_year_breakdown = list(
            bench_entries.exclude(judgment__date__isnull=True)
            .values("judgment__date__year")
            .annotate(judgment_count=Count("judgment", distinct=True))
            .order_by("-judgment__date__year")
        )
        context.update(
            self.get_filter_context(judge_court_breakdown, judge_year_breakdown)
        )
        if self.request.htmx:
            return context

        (
            context["judge_display_surname"],
            context["judge_display_name_remainder"],
        ) = split_judge_display_name(self.judge_person.full_name)
        context["judge_judgment_count"] = (
            bench_entries.values("judgment_id").distinct().count()
        )
        context["judge_first_year"] = (
            judge_year_breakdown[-1]["judgment__date__year"]
            if judge_year_breakdown
            else None
        )
        context["judge_latest_year"] = (
            judge_year_breakdown[0]["judgment__date__year"]
            if judge_year_breakdown
            else None
        )
        alias_records = list(self.judge_person.aliases.only("name", "title"))
        context["judge_aliases"] = [alias.name for alias in alias_records]
        context["judge_titles"] = sorted(
            {alias.title for alias in alias_records if alias.title}
        )
        context["judge_year_activity"] = percentage_chart_rows(
            [
                {
                    "year": row["judgment__date__year"],
                    "judgment_count": row["judgment_count"],
                }
                for row in reversed(judge_year_breakdown)
            ]
        )
        active_year_count = len(context["judge_year_activity"])
        context["judge_average_per_active_year"] = (
            round(context["judge_judgment_count"] / active_year_count, 1)
            if active_year_count
            else 0
        )
        context["judge_peak_year"] = max(
            context["judge_year_activity"],
            key=lambda row: row["judgment_count"],
            default=None,
        )
        context["judge_court_chart"] = percentage_chart_rows(
            [dict(row) for row in judge_court_breakdown]
        )
        context["judge_topic_chart"] = self.get_topic_chart()
        primary_court = judge_court_breakdown[0] if judge_court_breakdown else None
        context.update(self.get_primary_court_context(primary_court))
        context["judge_citation_analysis"] = self.get_citation_analysis(bench_entries)
        return context


class JudgeIdentityWorkflowMixin:
    model = JudgePerson
    workflow_limit = 200
    template_name = "admin/peachjam/judge_identity/workflow_change_form.html"
    alias_tab = "aliases"
    judge_people_tab = "judge_people"

    def get_workflow_initial(self, request):
        initial = {}
        judge_person_id = request.GET.get("judge_person")
        if judge_person_id:
            initial["target_judge_person"] = judge_person_id
            initial["merge_target_judge_person"] = judge_person_id
        return initial

    def get_active_tab(
        self,
        request,
        selected_alias_ids,
        selected_judge_person_ids,
        form=None,
    ):
        requested_tab = (
            request.POST.get("tab") or request.GET.get("tab") or ""
        ).strip()
        if requested_tab in {self.alias_tab, self.judge_people_tab}:
            active_tab = requested_tab
        elif selected_judge_person_ids and not selected_alias_ids:
            active_tab = self.judge_people_tab
        else:
            active_tab = self.alias_tab

        if form is None or not form.errors:
            return active_tab

        if form["selected_aliases"].errors:
            return self.alias_tab
        if (
            form["selected_judge_people"].errors
            or form["merge_target_judge_person"].errors
        ):
            return self.judge_people_tab
        return active_tab

    def get_alias_workflow_rows(self, query):
        alias_qs = JudgeAlias.objects.select_related("judge_person").order_by(
            "name",
            "pk",
        )
        if query:
            alias_qs = alias_qs.filter(
                Q(name__icontains=query)
                | Q(title__icontains=query)
                | Q(normalized_name__icontains=query)
                | Q(judge_person__full_name__icontains=query)
            ).distinct()

        aliases = list(alias_qs[: self.workflow_limit])
        alias_ids = [alias.pk for alias in aliases]
        alias_names = [alias.name for alias in aliases]

        alias_duplicates = {
            row["name"]: row["count"]
            for row in JudgeAlias.objects.filter(name__in=alias_names)
            .values("name")
            .annotate(count=Count("pk"))
        }
        legacy_judges = {
            judge.name: judge
            for judge in Judge.objects.filter(name__in=alias_names).order_by("pk")
        }

        bench_stats = {
            row["matched_alias_id"]: row
            for row in Bench.objects.filter(matched_alias_id__in=alias_ids)
            .values("matched_alias_id")
            .annotate(
                bench_rows=Count("pk"),
                judgments=Count("judgment_id", distinct=True),
            )
        }

        rows = []
        for alias in aliases:
            stats = bench_stats.get(alias.pk, {})
            legacy_judge = legacy_judges.get(alias.name)

            if alias_duplicates.get(alias.name, 0) > 1:
                status = "Conflict"
                status_class = "warning"
            elif stats.get("bench_rows", 0):
                status = "Mapped"
                status_class = "success"
            elif legacy_judge is not None:
                status = "Alias only"
                status_class = "info"
            else:
                status = "Orphan"
                status_class = "secondary"

            notes = []
            if alias_duplicates.get(alias.name, 0) > 1:
                notes.append(
                    gettext_lazy(
                        "{} alias records currently share this exact name."
                    ).format(alias_duplicates[alias.name])
                )
            if legacy_judge is None:
                notes.append(
                    gettext_lazy(
                        "No matching legacy Judge row exists for this alias name."
                    )
                )

            rows.append(
                {
                    "alias": alias,
                    "legacy_judge": legacy_judge,
                    "current_person": alias.judge_person,
                    "status": status,
                    "status_class": status_class,
                    "bench_rows": stats.get("bench_rows", 0),
                    "judgments": stats.get("judgments", 0),
                    "notes": notes,
                }
            )

        return rows

    def get_judge_person_workflow_rows(self, query):
        judge_person_qs = JudgePerson.objects.order_by("full_name", "pk").annotate(
            alias_count=Count("aliases", distinct=True),
            bench_rows=Count("bench_entries", distinct=True),
            judgments=Count("bench_entries__judgment_id", distinct=True),
        )
        if query:
            judge_person_qs = judge_person_qs.filter(
                Q(full_name__icontains=query) | Q(aliases__name__icontains=query)
            ).distinct()

        rows = []
        for judge_person in judge_person_qs[: self.workflow_limit]:
            if judge_person.alias_count == 0 and judge_person.bench_rows == 0:
                status = "Empty"
                status_class = "secondary"
            elif judge_person.alias_count == 0:
                status = "Conflict"
                status_class = "warning"
            elif judge_person.bench_rows == 0:
                status = "Alias only"
                status_class = "info"
            else:
                status = "In use"
                status_class = "success"

            notes = []
            if judge_person.alias_count == 0 and judge_person.bench_rows:
                notes.append(
                    gettext_lazy(
                        "Bench rows still point here, but this judge person has no aliases."
                    )
                )
            if judge_person.alias_count and judge_person.bench_rows == 0:
                notes.append(
                    gettext_lazy("This judge person currently owns aliases only.")
                )

            rows.append(
                {
                    "judge_person": judge_person,
                    "alias_count": judge_person.alias_count,
                    "bench_rows": judge_person.bench_rows,
                    "judgments": judge_person.judgments,
                    "status": status,
                    "status_class": status_class,
                    "notes": notes,
                }
            )

        return rows

    def apply_workflow(self, cleaned_data):
        action = cleaned_data["action"]
        handlers = {
            JudgeIdentityWorkflowForm.APPLY_IDENTITY_CHANGES: self.apply_identity_changes,
            JudgeIdentityWorkflowForm.MERGE_JUDGE_PEOPLE: self.merge_selected_judge_people,
            JudgeIdentityWorkflowForm.DELETE_RECORDS: self.delete_selected_records,
        }
        try:
            return handlers[action](cleaned_data)
        except KeyError as exc:
            raise ValidationError(gettext_lazy("Choose a workflow action.")) from exc

    def apply_identity_changes(self, cleaned_data):
        with transaction.atomic():
            selected_aliases = list(cleaned_data["selected_aliases"])
            judge_person = cleaned_data["target_judge_person"]
            requested_name = cleaned_data["target_full_name"]
            created = False
            renamed = False
            old_name = None
            if judge_person is None:
                judge_person, created = (
                    judge_identity_service.get_or_create_judge_person(requested_name)
                )

            source_judge_people = set()
            moved_count = len(selected_aliases)
            if selected_aliases:
                source_judge_people = {
                    judge_alias.judge_person
                    for judge_alias in selected_aliases
                    if judge_alias.judge_person_id
                    and judge_alias.judge_person_id != judge_person.pk
                }
                for judge_alias in selected_aliases:
                    judge_identity_service.move_judge_alias_to_person(
                        judge_alias, judge_person
                    )

            if requested_name and judge_person.full_name != requested_name:
                old_name = judge_person.full_name
                judge_identity_service.rename_judge_person(judge_person, requested_name)
                renamed = True

            deleted_count = 0
            for source_judge_person in source_judge_people:
                source_judge_person.refresh_from_db()
                if (
                    not source_judge_person.aliases.exists()
                    and not source_judge_person.bench_entries.exists()
                ):
                    source_judge_person.delete()
                    deleted_count += 1

        return {
            "action": JudgeIdentityWorkflowForm.APPLY_IDENTITY_CHANGES,
            "judge_person": judge_person,
            "created": created,
            "renamed": renamed,
            "old_name": old_name,
            "count": moved_count,
            "deleted_count": deleted_count,
        }

    def merge_selected_judge_people(self, cleaned_data):
        with transaction.atomic():
            judge_person = cleaned_data["merge_target_judge_person"]
            duplicates = [
                candidate
                for candidate in cleaned_data["selected_judge_people"]
                if candidate.pk != judge_person.pk
            ]
            judge_identity_service.merge_judge_people(judge_person, duplicates)

        return {
            "action": JudgeIdentityWorkflowForm.MERGE_JUDGE_PEOPLE,
            "judge_person": judge_person,
            "count": len(duplicates),
        }

    def delete_selected_records(self, cleaned_data):
        with transaction.atomic():
            delete_mode = cleaned_data.get("delete_mode") or "aliases"
            selected_aliases = list(cleaned_data["selected_aliases"])
            selected_judge_people = list(cleaned_data["selected_judge_people"])
            selected_judge_person_ids = {
                judge_person.pk for judge_person in selected_judge_people
            }
            selected_alias_count = 0
            judge_people_result = {
                "judge_person_count": 0,
                "alias_count": 0,
                "cleared_matched_alias_count": 0,
                "cleared_judge_person_count": 0,
            }

            if delete_mode in {"aliases", "both"}:
                if delete_mode == "both":
                    selected_aliases = [
                        judge_alias
                        for judge_alias in selected_aliases
                        if judge_alias.judge_person_id not in selected_judge_person_ids
                    ]
                alias_result = judge_identity_service.delete_judge_aliases(
                    selected_aliases
                )
                selected_alias_count = alias_result["alias_count"]
            else:
                alias_result = {
                    "alias_count": 0,
                    "cleared_matched_alias_count": 0,
                }

            if delete_mode in {"judge_people", "both"}:
                judge_people_result = judge_identity_service.delete_judge_people(
                    selected_judge_people
                )

        return {
            "action": JudgeIdentityWorkflowForm.DELETE_RECORDS,
            "judge_person": None,
            "alias_count": selected_alias_count + judge_people_result["alias_count"],
            "judge_person_count": judge_people_result["judge_person_count"],
            "cleared_matched_alias_count": (
                alias_result["cleared_matched_alias_count"]
                + judge_people_result["cleared_matched_alias_count"]
            ),
            "cleared_judge_person_count": judge_people_result[
                "cleared_judge_person_count"
            ],
        }

    def build_workflow_success_message(self, result):
        action = result["action"]
        judge_person = result.get("judge_person")

        if action == JudgeIdentityWorkflowForm.APPLY_IDENTITY_CHANGES:
            change_url = reverse(
                "admin:peachjam_judgeperson_change",
                args=[quote(judge_person.pk)],
            )
            if result["count"] == 0 and result["renamed"]:
                return format_html(
                    'Renamed judge person "{}" to <a href="{}">{}</a>.',
                    result["old_name"],
                    change_url,
                    judge_person.full_name,
                )
            if result["count"] == 0:
                return gettext_lazy("No judge identity changes were applied.")

            action_label = (
                gettext_lazy("Created judge person")
                if result["created"]
                else gettext_lazy("Updated judge person")
            )
            summary = gettext_lazy(
                "Moved {} selected aliases to this judge person, refreshed their "
                "bench links automatically, and deleted {} now-empty source judge "
                "people."
            )
            if result["renamed"]:
                return format_html(
                    '{} <a href="{}">{}</a>. Moved {} selected aliases to this '
                    "judge person, refreshed their bench links automatically, "
                    "deleted {} now-empty source judge people, and renamed the "
                    'judge person from "{}".',
                    action_label,
                    change_url,
                    judge_person.full_name,
                    result["count"],
                    result["deleted_count"],
                    result["old_name"],
                )
            summary = summary.format(result["count"], result["deleted_count"])
            return format_html(
                '{} <a href="{}">{}</a>. {}',
                action_label,
                change_url,
                judge_person.full_name,
                summary,
            )

        if action == JudgeIdentityWorkflowForm.MERGE_JUDGE_PEOPLE:
            change_url = reverse(
                "admin:peachjam_judgeperson_change",
                args=[quote(judge_person.pk)],
            )
            return format_html(
                'Merged {} selected judge people into <a href="{}">{}</a>.',
                result["count"],
                change_url,
                judge_person.full_name,
            )

        if action == JudgeIdentityWorkflowForm.DELETE_RECORDS:
            message_bits = []
            if result["alias_count"]:
                message_bits.append(
                    gettext_lazy("Deleted {} aliases").format(result["alias_count"])
                )
            if result["judge_person_count"]:
                message_bits.append(
                    gettext_lazy("Deleted {} judge people").format(
                        result["judge_person_count"]
                    )
                )
            if result["cleared_matched_alias_count"]:
                message_bits.append(
                    gettext_lazy("Cleared {} matched alias links on bench rows").format(
                        result["cleared_matched_alias_count"]
                    )
                )
            if result["cleared_judge_person_count"]:
                message_bits.append(
                    gettext_lazy("Cleared {} judge person links on bench rows").format(
                        result["cleared_judge_person_count"]
                    )
                )
            if not message_bits:
                message_bits.append(gettext_lazy("No records were deleted"))
            return " ".join(f"{message}." for message in message_bits)

        return gettext_lazy("Judge identity workflow completed.")


@method_decorator(staff_member_required, name="dispatch")
class JudgeIdentityWorkflowView(JudgeIdentityWorkflowMixin, TemplateView):
    def dispatch(self, request, *args, **kwargs):
        if not JudgePerson.canonical_identity_enabled() or not request.user.has_perm(
            "peachjam.change_judgeperson"
        ):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return self.render_workflow(request)

    def post(self, request, *args, **kwargs):
        return self.render_workflow(request)

    def render_workflow(self, request):
        query = (request.GET.get("q") or request.POST.get("q") or "").strip()
        selected_alias_ids = request.POST.getlist("selected_aliases")
        selected_judge_person_ids = request.POST.getlist("selected_judge_people")

        if not selected_judge_person_ids and request.GET.get("judge_person"):
            selected_judge_person_ids = [request.GET["judge_person"]]

        if request.method == "POST":
            form = JudgeIdentityWorkflowForm(request.POST)
            if form.is_valid():
                result = self.apply_workflow(form.cleaned_data)
                messages.success(
                    request,
                    self.build_workflow_success_message(result),
                )
                redirect_url = reverse("peachjam_judgeperson_workflow")
                params = {}
                if query:
                    params["q"] = query
                active_tab = self.get_active_tab(
                    request,
                    selected_alias_ids,
                    selected_judge_person_ids,
                )
                if active_tab != self.alias_tab:
                    params["tab"] = active_tab
                if result.get("judge_person") is not None:
                    params["judge_person"] = result["judge_person"].pk
                query_string = f"?{urlencode(params)}" if params else ""
                return HttpResponseRedirect(f"{redirect_url}{query_string}")
        else:
            form = JudgeIdentityWorkflowForm(initial=self.get_workflow_initial(request))

        active_tab = self.get_active_tab(
            request,
            selected_alias_ids,
            selected_judge_person_ids,
            form=form,
        )
        alias_workflow_rows = self.get_alias_workflow_rows(query)
        judge_person_workflow_rows = self.get_judge_person_workflow_rows(query)
        context = {
            **admin.site.each_context(request),
            "opts": self.model._meta,
            "title": gettext_lazy("Judge identity workflow"),
            "subtitle": None,
            "form": form,
            "media": form.media,
            "query": query,
            "selected_alias_ids": selected_alias_ids,
            "selected_judge_person_ids": selected_judge_person_ids,
            "alias_workflow_rows": alias_workflow_rows,
            "judge_person_workflow_rows": judge_person_workflow_rows,
            "workflow_limit": self.workflow_limit,
            "active_tab": active_tab,
            "alias_tab": self.alias_tab,
            "judge_people_tab": self.judge_people_tab,
        }
        return TemplateResponse(request, self.template_name, context)
