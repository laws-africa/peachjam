from itertools import groupby

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.dates import MONTHS

from peachjam.helpers import chunks, lowercase_alphabet
from peachjam.models import Court, CourtClass, CourtRegistry, Judgment
from peachjam.views.generic_views import FilteredDocumentListView


class BaseJudgmentFilterView(FilteredDocumentListView):
    """Base List View class for filtering judgments."""

    model = Judgment
    navbar_link = "judgments"
    queryset = Judgment.objects.prefetch_related("judges", "labels")

    def base_view_name(self):
        return "Judgments"

    def page_title(self):
        return self.base_view_name()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["doc_type"] = "Judgment"
        context["page_title"] = self.page_title()

        if not self.form.cleaned_data.get("alphabet"):
            context["grouped_documents"] = self.grouped_judgments(context["documents"])

        self.populate_years(context)
        self.populate_facets(context)

        return context

    def populate_facets(self, context):
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

        order_outcomes = list(
            order_outcome
            for order_outcome in self.form.filter_queryset(
                self.get_base_queryset(), exclude="order_outcomes"
            )
            .order_by()
            .values_list("order_outcomes__name", flat=True)
            .distinct()
            if order_outcome
        )

        context["facet_data"] = {
            "judges": judges,
            "alphabet": lowercase_alphabet(),
            "attorneys": attorneys,
            "order_outcomes": order_outcomes,
        }

    def populate_years(self, context):
        context["years"] = self.get_base_queryset(exclude=["year", "month"]).dates(
            "date", "year", order="DESC"
        )

    def grouped_judgments(self, documents):
        """Group the judgments by month and return a list of dicts with the month name and judgments for that month"""
        # Group documents by month
        groups = groupby(documents, lambda d: f"{MONTHS[d.date.month]} {d.date.year}")

        return [{"key": key, "judgments": list(group)} for key, group in groups]


class CourtDetailView(BaseJudgmentFilterView):
    template_name = "peachjam/court_detail.html"

    @property
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
        context["registries"] = self.court.registries.exclude(
            judgments__isnull=True
        )  # display registries with judgments only
        context["registry_groups"] = list(chunks(context["registries"], 2))
        return context


class YearMixin:
    @property
    def year(self):
        return self.kwargs["year"]

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
        context["year"] = self.year
        self.populate_months(context)
        return context

    def populate_months(self, context):
        context["months"] = self.get_base_queryset(exclude=["month"]).dates(
            "date", "month", order="ASC"
        )


class CourtYearView(YearMixin, CourtDetailView):
    pass


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

    @property
    def registry(self):
        return get_object_or_404(CourtRegistry, code=self.kwargs.get("registry_code"))

    def get_base_queryset(self, *args, **kwargs):
        return super().get_base_queryset(*args, **kwargs).filter(registry=self.registry)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["registry"] = self.registry
        return context


class CourtRegistryDetailView(RegistryMixin, CourtDetailView):
    pass


class CourtRegistryYearView(RegistryMixin, CourtYearView):
    pass


class CourtRegistryMonthView(RegistryMixin, CourtMonthView):
    pass


class CourtClassDetailView(BaseJudgmentFilterView):
    template_name = "peachjam/court_class_detail.html"

    def base_view_name(self):
        return self.court_class.name

    @property
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
        context["registry_groups"] = list(chunks(context["registries"], 2))
        return context


class CourtClassYearView(YearMixin, CourtClassDetailView):
    pass


class CourtClassMonthView(MonthMixin, CourtClassYearView):
    pass
