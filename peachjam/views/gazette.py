from itertools import groupby
from operator import itemgetter

from django.db.models import Count
from django.db.models.functions import ExtractMonth, ExtractYear
from django.utils.dates import MONTHS
from django.views.generic import TemplateView

from peachjam.models import Gazette
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


def group_years(years):
    # sort list of years
    years.sort(key=lambda x: x["year"])

    results = []
    # group list of years dict by year
    for key, value in groupby(years, key=itemgetter("year")):
        year_dict = {"year": key, "count": sum(int(x["count"]) for x in value)}
        results.append(year_dict)
    return results


class GazetteListView(TemplateView):
    model = Gazette
    template_name = "peachjam/gazette_list.html"

    def get_queryset(self):
        return self.model.objects

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        queryset = self.get_queryset()
        context["num_gazettes"] = queryset.count()
        context["years"] = self.get_year_stats(queryset)

        return context

    def get_year_stats(self, queryset):
        years = list(
            queryset.annotate(
                year=ExtractYear("date"), month=ExtractMonth("date"), count=Count("pk")
            ).values("year", "month", "count")
        )
        return group_years(years)


class GazetteYearView(FilteredDocumentListView):
    model = Gazette
    template_name = "peachjam/gazette_year.html"
    paginate_by = 0

    def get_queryset(self):
        return super().get_queryset().filter(date__year=self.kwargs["year"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        years = list(
            self.get_base_queryset()
            .annotate(
                year=ExtractYear("date"),
                count=Count("pk"),
            )
            .values("year", "count")
        )
        context["years"] = group_years(years)
        context["gazettes"] = self.group_gazettes(list(self.get_queryset()))
        context["year"] = int(self.kwargs["year"])

        return context

    def group_gazettes(self, gazettes):
        months = {m: [] for m in range(1, 13)}

        for month, group in groupby(gazettes, key=lambda g: g.date.month):
            months[month] = list(group)

        # (month number, [list of gazettes]) tuples
        months = [(m, v) for m, v in months.items()]
        months.sort(key=lambda x: x[0])
        months = [(MONTHS[m], v) for m, v in months]

        return months


@registry.register_doc_type("gazette")
class GenericDocumentDetailView(BaseDocumentDetailView):
    model = Gazette
    template_name = "peachjam/gazette_detail.html"
