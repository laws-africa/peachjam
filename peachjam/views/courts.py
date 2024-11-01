from functools import cached_property
from math import ceil

from django.core.cache import cache
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.dates import MONTHS
from django.utils.text import gettext_lazy as _
from django.utils.text import slugify

from peachjam.helpers import chunks, lowercase_alphabet
from peachjam.models import (
    Court,
    CourtClass,
    CourtRegistry,
    Judge,
    Judgment,
    Outcome,
    Taxonomy,
)
from peachjam.views.generic_views import FilteredDocumentListView, YearListMixin


class FilteredJudgmentView(FilteredDocumentListView):
    """Base List View class for filtering judgments."""

    model = Judgment
    navbar_link = "judgments"
    queryset = Judgment.objects.prefetch_related(
        "judges", "labels", "attorneys", "outcomes"
    ).select_related("work")
    exclude_facets = []
    group_by_date = "month-year"

    def get_form(self):
        self.form_defaults = {"sort": "-date"}
        return super().get_form()

    def base_view_name(self):
        return _("Judgments")

    def page_title(self):
        return self.base_view_name()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["nature"] = "Judgment"
        context["page_title"] = self.page_title()
        context["doc_table_show_jurisdiction"] = False
        context["doc_table_title_label"] = _("Citation")
        context["doc_table_date_label"] = _("Judgment date")
        context["doc_count_noun"] = _("judgment")
        context["doc_count_noun_plural"] = _("judgments")

        self.populate_years(context)
        context["documents"] = self.group_documents(context["documents"])

        return context

    def add_facets(self, context):
        context["facet_data"] = {}
        if "judges" not in self.exclude_facets:
            judges = list(
                judge
                for judge in self.form.filter_queryset(
                    self.get_base_queryset(), exclude="judges"
                )
                .order_by()
                .values_list("judges__name", flat=True)
                .distinct()
                if judge
            )
            context["facet_data"]["judges"] = {
                "label": Judge.model_label_plural,
                "type": "checkbox",
                "options": sorted([(j, j) for j in judges]),
                "values": self.request.GET.getlist("judges"),
            }

        if "outcomes" not in self.exclude_facets:
            outcomes = Outcome.objects.filter(
                pk__in=self.form.filter_queryset(
                    self.get_base_queryset(), exclude="outcomes"
                )
                .order_by()
                .values_list("outcomes__id", flat=True)
                .distinct()
            )
            context["facet_data"]["outcomes"] = {
                "label": _("Outcomes"),
                "type": "checkbox",
                "options": sorted(
                    [(outcome.name, outcome.name) for outcome in outcomes]
                ),
                "values": self.request.GET.getlist("outcomes"),
            }

        if "attorneys" not in self.exclude_facets:
            attorneys = list(
                attorney
                for attorney in self.form.filter_queryset(
                    self.get_base_queryset(), exclude="attorneys"
                )
                .order_by()
                .values_list("attorneys__name", flat=True)
                .distinct()
                if attorney
            )
            context["facet_data"]["attorneys"] = {
                "label": _("Attorneys"),
                "type": "checkbox",
                "options": sorted([(a, a) for a in attorneys]),
                "values": self.request.GET.getlist("attorneys"),
            }

        if "taxonomy" not in self.exclude_facets:
            taxonomies = Taxonomy.objects.filter(
                pk__in=self.form.filter_queryset(
                    self.get_base_queryset(), exclude="taxonomies"
                )
                .filter(taxonomies__topic__isnull=False)
                .order_by("taxonomies__topic__id")
                .values_list("taxonomies__topic__id", flat=True)
                .distinct()
            )

            context["facet_data"]["taxonomies"] = {
                "label": _("Topics"),
                "type": "checkbox",
                "options": sorted(
                    [(t.slug, t.name) for t in taxonomies], key=lambda x: x[1]
                ),
                "values": self.request.GET.getlist("taxonomies"),
            }

        if "alphabet" not in self.exclude_facets:
            context["facet_data"]["alphabet"] = {
                "label": _("Alphabet"),
                "type": "radio",
                "options": [(a, a) for a in lowercase_alphabet()],
                "values": self.request.GET.get("alphabet"),
            }

    def populate_years(self, context):
        cache_key = f"judgment_years_{slugify(self.base_view_name())}"
        years = cache.get(cache_key)
        if years is None:
            years = self.get_base_queryset(exclude=["year", "month"]).dates(
                "date", "year", order="DESC"
            )
            cache.set(cache_key, years)
        context["years"] = years


class CourtDetailView(FilteredJudgmentView):
    template_name = "peachjam/court_detail.html"

    @cached_property
    def court(self):
        return get_object_or_404(Court, code=self.kwargs.get("code"))

    def base_view_name(self):
        return self.court.name

    def get_base_queryset(self, exclude=None):
        qs = super().get_base_queryset(exclude=exclude).filter(court=self.court)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["court"] = self.court
        context["registry_label_plural"] = CourtRegistry.model_label_plural
        context["registries"] = registries = self.court.registries.exclude(
            judgments__isnull=True
        )  # display registries with judgments only
        # split the list in the middle to have two columns and preserve ordering
        split_index = ceil(registries.count() / 2)
        context["registry_groups"] = [
            registries[:split_index],
            registries[split_index:],
        ]

        context["all_years_url"] = self.court.get_absolute_url()
        return context

    def add_entity_profile(self, context):
        context["entity_profile"] = self.court.entity_profile.first()
        context["entity_profile_title"] = self.court.name


class CourtYearView(YearListMixin, CourtDetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_months_url"] = reverse(
            "court_year", args=[self.court.code, self.year]
        )
        return context


class MonthMixin:
    @property
    def month(self):
        if self.kwargs["month"] not in set(range(1, 13)):
            raise Http404("Invalid month")
        return self.kwargs["month"]

    def page_title(self):
        return f"{super().page_title()} {MONTHS[self.month]}"

    def get_base_queryset(self, exclude=None):
        if exclude is None:
            exclude = []
        qs = super().get_base_queryset(exclude=exclude)
        if "month" not in exclude:
            qs = qs.filter(date__month=self.month)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["month"] = MONTHS[self.month]
        return context


class CourtMonthView(MonthMixin, CourtYearView):
    pass


class RegistryMixin:
    template_name = "peachjam/court_registry_detail.html"

    def base_view_name(self):
        return self.registry.name

    @cached_property
    def registry(self):
        return get_object_or_404(CourtRegistry, code=self.kwargs.get("registry_code"))

    def get_base_queryset(self, *args, **kwargs):
        return super().get_base_queryset(*args, **kwargs).filter(registry=self.registry)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["registry"] = self.registry
        context["all_years_url"] = self.registry.get_absolute_url()
        return context


class CourtRegistryDetailView(RegistryMixin, CourtDetailView):
    pass


class CourtRegistryYearView(YearListMixin, CourtRegistryDetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_months_url"] = reverse(
            "court_registry_year", args=[self.court.code, self.registry.code, self.year]
        )
        return context


class CourtRegistryMonthView(MonthMixin, CourtRegistryYearView):
    pass


class CourtClassDetailView(FilteredJudgmentView):
    template_name = "peachjam/court_class_detail.html"

    def base_view_name(self):
        return self.court_class.name

    @cached_property
    def court_class(self):
        return get_object_or_404(CourtClass, slug=self.kwargs["court_class"])

    def get_base_queryset(self, exclude=None):
        return (
            super()
            .get_base_queryset(exclude=exclude)
            .filter(court__court_class=self.court_class)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["court_class"] = self.court_class
        context["registries"] = Court.objects.filter(court_class=self.court_class)
        context["registry_label_plural"] = _("Courts")
        context["registry_groups"] = list(chunks(context["registries"], 2))
        context["all_years_url"] = self.court_class.get_absolute_url()

        return context


class CourtClassYearView(YearListMixin, CourtClassDetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_months_url"] = reverse(
            "court_class_year", args=[self.court_class.slug, self.year]
        )
        return context


class CourtClassMonthView(MonthMixin, CourtClassYearView):
    pass
