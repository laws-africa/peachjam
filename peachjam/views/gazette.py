from itertools import groupby

from django.db.models import Count
from django.db.models.functions import ExtractMonth, ExtractYear
from django.urls import reverse
from django.utils.dates import MONTHS
from django.views.generic import TemplateView

from peachjam.helpers import chunks
from peachjam.models import Gazette, Locality, get_country_and_locality_or_404
from peachjam.registry import registry
from peachjam.views.generic_views import BaseDocumentDetailView, DocumentListView


def year_and_month_aggs(queryset, place_code=None):
    """Group and count items by year and month."""
    results = []

    items = list(
        queryset.annotate(
            year=ExtractYear("date"), month=ExtractMonth("date"), count=Count("pk")
        ).values("year", "month", "count")
    )

    # sort by years and months
    items.sort(key=lambda x: x["year"], reverse=True)
    for year, year_group in groupby(items, key=lambda x: x["year"]):
        year_group = list(year_group)

        month_counts = [0] * 12
        for month, month_group in groupby(
            sorted(year_group, key=lambda x: x["month"]), key=lambda x: x["month"]
        ):
            month_counts[month - 1] = sum(x["count"] for x in month_group)

        months = [
            {
                "month": month,
                "label": MONTHS[month],
                "count": count,
            }
            for month, count in enumerate(month_counts, 1)
        ]

        results.append(
            {
                "year": year,
                "count": sum(x["count"] for x in year_group),
                "months": months,
                "month_max": max(month_counts),
                "url": reverse(
                    "gazettes_by_year",
                    args=[place_code, year] if place_code else [year],
                ),
            }
        )

    return results


class GazetteListView(TemplateView):
    queryset = Gazette.objects.filter(published=True)
    template_name = "peachjam/gazette_list.html"
    navbar_link = "gazettes"

    def get(self, request, code=None, *args, **kwargs):
        self.country, self.locality = get_country_and_locality_or_404(code)
        self.place = self.locality or self.country
        return super().get(request, *args, **kwargs)

    def get_base_queryset(self):
        return self.queryset

    def get_queryset(self):
        qs = self.get_base_queryset().filter(locality=self.locality)
        if self.country:
            qs = qs.filter(jurisdiction=self.country)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(
            locality=self.locality, country=self.country, place=self.place, **kwargs
        )

        context["localities"] = self.get_localities(context)
        context["locality_groups"] = list(chunks(context["localities"], 2))
        queryset = self.get_queryset()
        context["years"] = year_and_month_aggs(queryset, self.kwargs.get("code"))
        context["doc_count"] = queryset.count()
        context["doc_type"] = "Gazette"

        return context

    def get_localities(self, context):
        if self.locality is None:
            locality_ids = list(
                self.get_base_queryset()
                .order_by()
                .distinct("locality")
                .values_list("locality", flat=True)
            )
            return Locality.objects.filter(pk__in=locality_ids)
        return []


class GazetteYearView(DocumentListView):
    model = Gazette
    queryset = Gazette.objects.prefetch_related("source_file").order_by("date")
    template_name = "peachjam/gazette_year.html"
    paginate_by = 0
    navbar_link = "gazettes"
    locality = None

    def get(self, request, code=None, *args, **kwargs):
        self.country, self.locality = get_country_and_locality_or_404(code)
        self.place = self.locality or self.country
        return super().get(request, *args, **kwargs)

    def get_base_queryset(self):
        qs = super().get_base_queryset().filter(locality=self.locality)
        if self.country:
            qs = qs.filter(jurisdiction=self.country)
        return qs

    def get_queryset(self):
        return super().get_queryset().filter(date__year=self.kwargs["year"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(
            place=self.place, country=self.country, locality=self.locality, **kwargs
        )

        context["gazettes"] = self.group_gazettes(list(self.object_list))
        context["year"] = int(self.kwargs["year"])
        context["years"] = year_and_month_aggs(
            self.get_base_queryset(), self.kwargs.get("code")
        )
        context["doc_type"] = "Gazette"
        context["doc_count"] = len(self.object_list)

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
class GazetteDetailView(BaseDocumentDetailView):
    model = Gazette
    template_name = "peachjam/gazette_detail.html"
    navbar_link = "gazettes"
