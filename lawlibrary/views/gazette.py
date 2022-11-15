from itertools import groupby
from operator import itemgetter

from django.db.models import Count
from django.db.models.functions import ExtractMonth, ExtractYear
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from peachjam.models import Gazette, Locality


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
    template_name = "lawlibrary/gazette_list.html"
    codes = "mp ec nc kzn gp wc lim nw fs".split()
    queryset = Gazette.objects.filter(locality__code__in=codes)
    provinces = Locality.objects.filter(code__in=codes)
    model = Gazette

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        groups = self.provinces[:5], self.provinces[5:]
        context["province_groups"] = groups
        context["num_gazettes"] = self.queryset.count()
        context["results"] = self.get_year_stats()

        return context

    def get_year_stats(self):
        years = list(
            self.queryset.annotate(
                year=ExtractYear("date"), month=ExtractMonth("date"), count=Count("pk")
            ).values("year", "month", "count")
        )
        return group_years(years)


class YearView(TemplateView):
    template_name = "lawlibrary/year.html"
    model = Gazette
    MONTHS = "January February March April May June July August September October November December".split()

    def get(self, request, code=None, *args, **kwargs):
        context = self.get_context_data(**kwargs)

        if code is not None:
            locality = get_object_or_404(Locality, code=code)
            context["locality"] = locality
            years = list(
                self.model.objects.order_by("-date")
                .filter(locality=locality)
                .annotate(
                    year=ExtractYear("date"),
                    month=ExtractMonth("date"),
                    count=Count("pk"),
                )
                .values("year", "month", "count")
            )
            context["results"] = group_years(years)
            context["gazettes"] = self.group_gazettes(
                list(
                    self.model.objects.filter(
                        locality=locality, date__year=self.kwargs["year"]
                    )
                )
            )

        else:
            years = list(
                self.model.objects.order_by("-date")
                .annotate(
                    year=ExtractYear("date"),
                    month=ExtractMonth("date"),
                    count=Count("pk"),
                )
                .values("year", "month", "count")
            )
            context["results"] = group_years(years)
            context["gazettes"] = self.group_gazettes(
                list(self.model.objects.filter(date__year=self.kwargs["year"]))
            )

        context["year"] = int(self.kwargs["year"])

        return self.render_to_response(context)

    def group_gazettes(self, gazettes):
        months = {m: [] for m in range(1, 13)}

        for month, group in groupby(gazettes, key=lambda g: g.date.month):
            months[month] = list(group)

        # (month number, [list of gazettes]) tuples
        months = [(m, v) for m, v in months.items()]
        months.sort(key=lambda x: x[0])
        months = [(self.MONTHS[m - 1], v) for m, v in months]

        return months


class ProvincialGazetteListView(TemplateView):
    template_name = "lawlibrary/provincial_gazette_list.html"
    model = Gazette

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)

        context["locality"] = locality = get_object_or_404(
            Locality, code=self.kwargs["code"]
        )
        context["num_gazettes"] = self.model.objects.filter(locality=locality).count()

        years = list(
            self.model.objects.filter(locality=locality)
            .annotate(
                year=ExtractYear("date"), month=ExtractMonth("date"), count=Count("pk")
            )
            .values("year", "month", "count")
        )

        context["results"] = group_years(years)

        return self.render_to_response(context)
