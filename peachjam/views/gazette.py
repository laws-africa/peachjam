from itertools import groupby
from operator import itemgetter

from django.db.models import Count
from django.db.models.functions import ExtractMonth, ExtractYear
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.dates import MONTHS
from django.views.generic import TemplateView

from peachjam.helpers import chunks
from peachjam.models import Gazette, Locality
from peachjam.registry import registry
from peachjam.views.generic_views import BaseDocumentDetailView, DocumentListView


def group_years(years, locality={}):
    # sort list of years
    years.sort(key=lambda x: x["year"], reverse=True)

    results = []
    # group list of years dict by year
    for key, value in groupby(years, key=itemgetter("year")):
        year_dict = {
            "year": key,
            "count": sum(int(x["count"]) for x in value),
            "url": reverse(
                "gazettes_by_year",
                args=[locality.code, key] if locality else [key],
            ),
        }
        results.append(year_dict)
    return results


class GazetteListView(TemplateView):
    queryset = Gazette.objects.exclude(published=False).prefetch_related("source_file")
    template_name = "peachjam/gazette_list.html"
    navbar_link = "gazettes"

    def get(self, request, code=None, *args, **kwargs):
        self.locality = get_object_or_404(Locality, code=code) if code else None
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = self.queryset
        if self.locality:
            qs = qs.filter(locality=self.locality)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(locality=self.locality, **kwargs)

        queryset = self.get_queryset()

        context["localities"] = []
        if self.locality is None:
            locality_ids = list(
                queryset.order_by()
                .distinct("locality")
                .values_list("locality", flat=True)
            )
            context["localities"] = Locality.objects.filter(pk__in=locality_ids)

        context["locality_groups"] = list(chunks(context["localities"], 2))

        if not self.locality:
            # counts and years for gazettes at the top-level?
            queryset = queryset.filter(locality=None)

        context["num_gazettes"] = queryset.count()
        context["years"] = self.get_year_stats(queryset)
        context["doc_type"] = "Gazette"

        return context

    def get_year_stats(self, queryset):
        years = list(
            queryset.annotate(
                year=ExtractYear("date"), month=ExtractMonth("date"), count=Count("pk")
            ).values("year", "month", "count")
        )
        return group_years(years)


class GazetteYearView(DocumentListView):
    model = Gazette
    queryset = (
        Gazette.objects.exclude(published=False)
        .prefetch_related("source_file")
        .order_by("-date")
    )
    template_name = "peachjam/gazette_year.html"
    paginate_by = 0
    navbar_link = "gazettes"
    locality = None

    def get(self, request, code=None, *args, **kwargs):
        self.locality = get_object_or_404(Locality, code=code) if code else None
        return super().get(request, *args, **kwargs)

    def get_base_queryset(self):
        qs = super().get_base_queryset()
        qs = qs.filter(locality=self.locality)
        return qs

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
        context["years"] = group_years(years, self.locality)
        context["locality"] = self.locality

        context["gazettes"] = self.group_gazettes(list(self.object_list))
        context["year"] = int(self.kwargs["year"])
        context["doc_type"] = "Gazette"

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
