from itertools import groupby

from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.dates import MONTHS

from peachjam.helpers import chunks, lowercase_alphabet
from peachjam.models import Court, CourtRegistry, Judgment
from peachjam.views.generic_views import FilteredDocumentListView


class CourtDetailView(FilteredDocumentListView):
    """List View class for filtering a court's judgments.

    This view may be restricted to a specific year.
    """

    model = Judgment
    template_name = "peachjam/court_detail.html"
    navbar_link = "judgments"
    queryset = Judgment.objects.prefetch_related("labels")

    def get_base_queryset(self):
        qs = super().get_base_queryset().filter(court=self.court)
        if "year" in self.kwargs:
            qs = qs.filter(date__year=self.kwargs["year"])

        if "month" in self.kwargs:
            qs = qs.filter(date__month=self.kwargs["month"])

        return qs

    def get_queryset(self):
        self.court = get_object_or_404(Court, code=self.kwargs["code"])
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["doc_type"] = "Judgment"
        context["court"] = self.court
        context["formatted_court_name"] = self.formatted_court_name()
        context["registries"] = self.court.registries.exclude(
            judgments__isnull=True
        )  # display registries with judgments only
        context["registry_groups"] = list(chunks(context["registries"], 2))

        if not self.form.cleaned_data.get("alphabet"):
            context["grouped_documents"] = self.grouped_judgments(context["documents"])

        if "year" in self.kwargs:
            context["year"] = self.kwargs["year"]

            if "month" in self.kwargs and self.kwargs["month"] in set(range(1, 13)):
                context["month"] = MONTHS[self.kwargs["month"]]
                context[
                    "formatted_court_name"
                ] = f"{context['formatted_court_name']} - {context['month']} {self.kwargs['year']}"
            else:
                context[
                    "formatted_court_name"
                ] = f"{context['formatted_court_name']} - {self.kwargs['year']}"

            self.populate_months(context)

        self.populate_years(context)
        self.populate_facets(context)

        return context

    def populate_facets(self, context):
        judges = list(
            {
                judge
                for judge in self.form.filter_queryset(
                    self.get_base_queryset(), exclude="judges"
                ).values_list("judges__name", flat=True)
                if judge
            }
        )

        attorneys = list(
            {
                attorney
                for attorney in self.form.filter_queryset(
                    self.get_base_queryset(), exclude="attorneys"
                ).values_list("attorneys__name", flat=True)
                if attorney
            }
        )

        order_outcomes = list(
            {
                order_outcome
                for order_outcome in self.form.filter_queryset(
                    self.get_base_queryset(), exclude="order_outcomes"
                ).values_list("order_outcome__name", flat=True)
                if order_outcome
            }
        )

        context["facet_data"] = {
            "judges": judges,
            "alphabet": lowercase_alphabet(),
            "attorneys": attorneys,
            "order_outcomes": order_outcomes,
        }

    def formatted_court_name(self):
        return self.court.name

    def populate_years(self, context):
        years = self.queryset.filter(court=self.court).dates(
            "date", "year", order="DESC"
        )
        context["years"] = [
            {
                "url": reverse("court_year", args=[self.court.code, year.year]),
                "year": year.year,
            }
            for year in years
        ]
        context["all_years_url"] = reverse("court", args=[self.court.code])

    def populate_months(self, context):
        year = self.kwargs["year"]
        months = self.queryset.filter(court=self.court, date__year=year).dates(
            "date", "month", order="ASC"
        )
        context["months"] = [
            {
                "url": reverse("court_month", args=[self.court.code, year, item.month]),
                "month": MONTHS[item.month],
            }
            for item in months
        ]
        context["all_months_url"] = reverse(
            "court_year", args=[self.court.code, self.kwargs["year"]]
        )

    def grouped_judgments(self, documents):
        """Group the judgments by month and return a list of dicts with the month name and judgments for that month"""
        # Group documents by month
        groups = groupby(documents, lambda d: f"{MONTHS[d.date.month]} {d.date.year}")

        return [{"key": key, "judgments": list(group)} for key, group in groups]


class CourtYearView(CourtDetailView):
    pass


class CourtMonthView(CourtDetailView):
    pass


class CourtRegistryDetailView(CourtDetailView):
    queryset = Judgment.objects.prefetch_related("judges", "labels")
    template_name = "peachjam/court_registry_detail.html"

    def get_base_queryset(self):
        return super().get_base_queryset().filter(registry=self.registry)

    def get_queryset(self):
        self.court = get_object_or_404(Court, code=self.kwargs["code"])
        self.registry = get_object_or_404(
            CourtRegistry, code=self.kwargs["registry_code"]
        )
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["registry"] = self.registry
        return context

    def formatted_court_name(self):
        return self.registry.name

    def populate_years(self, context):
        years = self.queryset.filter(registry=self.registry).dates(
            "date", "year", order="DESC"
        )
        context["years"] = [
            {
                "url": reverse(
                    "court_registry_year",
                    args=[self.court.code, self.registry.code, year.year],
                ),
                "year": year.year,
            }
            for year in years
        ]
        context["all_years_url"] = reverse(
            "court_registry", args=[self.court.code, self.registry.code]
        )

    def populate_months(self, context):
        year = self.kwargs["year"]
        months = self.queryset.filter(registry=self.registry, date__year=year).dates(
            "date", "month", order="ASC"
        )
        context["months"] = [
            {
                "url": reverse(
                    "court_registry_month",
                    args=[self.court.code, self.registry.code, year, item.month],
                ),
                "month": MONTHS[item.month],
            }
            for item in months
        ]
        context["all_months_url"] = reverse(
            "court_registry_year",
            args=[self.court.code, self.registry.code, self.kwargs["year"]],
        )


class CourtRegistryYearView(CourtRegistryDetailView):
    pass


class CourtRegistryMonthView(CourtRegistryDetailView):
    pass
