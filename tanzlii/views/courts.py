from django.urls import reverse
from django.utils.dates import MONTHS

from peachjam.views.courts import CourtDetailView as BaseCourtDetailView
from peachjam.views.courts import CourtRegistryDetailView as BaseCourtRegistryDetailView


def grouped_judgments(queryset):
    """Group the judgments by month and return a list of dicts with the month name and judgments for that month"""

    # Get the distinct months from the queryset
    months = queryset.dates("date", "month")

    # Create a list of { month: month_name, articles: [list of judgments] } dicts
    return [
        {
            "month": MONTHS[m.month],
            "judgments": queryset.filter(date__month=m.month),
        }
        for m in months
    ]


class CourtDetailView(BaseCourtDetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["grouped_judgments"] = grouped_judgments(self.get_base_queryset())

        if "year" in self.kwargs:
            context["months"] = self.populate_months(self.kwargs["year"])

        if "month" in self.kwargs:
            context["year"] = self.kwargs["year"]
            context["month"] = MONTHS[self.kwargs["month"]]
            context[
                "formatted_court_name"
            ] = f"{self.court.name} - {MONTHS[self.kwargs['month']]} {self.kwargs['year']}"
            context["all_months_url"] = reverse(
                "court_year", args=[self.court.code, self.kwargs["year"]]
            )

        return context

    def populate_months(self, year):
        months = super().queryset.filter(court=self.court).dates("date", "month")
        return [
            {
                "url": reverse("court_month", args=[self.court.code, year, m.month]),
                "month": MONTHS[m.month],
            }
            for m in months
            if m.year == year
        ]


class CourtYearView(CourtDetailView):
    pass


class CourtMonthView(CourtDetailView):
    pass


class CourtRegistryDetailView(BaseCourtRegistryDetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["grouped_judgments"] = grouped_judgments(self.get_base_queryset())

        if "year" in self.kwargs:
            context["year"] = self.kwargs["year"]
            context["formatted_court_name"] = f"{self.registry.name} - " + str(
                self.kwargs["year"]
            )
            context["months"] = self.populate_months(self.kwargs["year"])

        if "month" in self.kwargs:
            context["year"] = self.kwargs["year"]
            context["month"] = MONTHS[self.kwargs["month"]]
            context[
                "formatted_court_name"
            ] = f"{self.registry.name} - {MONTHS[self.kwargs['month']]} {self.kwargs['year']}"
            context["all_months_url"] = reverse(
                "court_registry_year",
                args=[self.court.code, self.registry.code, self.kwargs["year"]],
            )
        return context

    def populate_months(self, year):
        months = (
            super()
            .queryset.filter(registry=self.registry)
            .dates("date", "month", order="ASC")
        )
        return [
            {
                "url": reverse(
                    "court_registry_month",
                    args=[self.court.code, self.registry.code, year, m.month],
                ),
                "month": MONTHS[m.month],
            }
            for m in months
            if m.year == year
        ]


class CourtRegistryYearView(CourtRegistryDetailView):
    pass


class CourtRegistryMonthView(CourtRegistryDetailView):
    pass
