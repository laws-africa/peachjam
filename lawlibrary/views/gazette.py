from itertools import groupby

from django.db.models import Count
from django.db.models.functions import ExtractMonth, ExtractYear
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from peachjam.models import Gazette, Locality


class GazetteListView(TemplateView):
    template_name = "lawlibrary/gazette_list.html"
    codes = "mp ec nc kzn gp wc lim nw fs".split()
    queryset = Gazette.objects.filter(locality__code__in=codes)
    provinces = Locality.objects.filter(code__in=codes)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        groups = self.provinces[:5], self.provinces[5:]
        context["province_groups"] = groups
        context["num_gazettes"] = self.queryset.count()
        context["years"] = self.get_year_stats()
        print(context["years"])

        # {'year': 1989, 'month': 11, 'count': 1}

        return context

    def get_year_stats(self):
        return self.queryset.annotate(
            year=ExtractYear("date"), month=ExtractMonth("date"), count=Count("pk")
        ).values("year", "month", "count")


class YearView(TemplateView):
    template_name = "lawlibrary/year.html"
    model = Gazette
    MONTHS = "January February March April May June July August September October November December".split()

    def get(self, request, code=None, *args, **kwargs):
        context = self.get_context_data(**kwargs)

        if code is not None:
            locality = get_object_or_404(Locality, code=code)
            context["locality"] = locality
            context["years"] = (
                self.model.objects.order_by("-date")
                .filter(locality=locality)
                .annotate(
                    year=ExtractYear("date"),
                    month=ExtractMonth("date"),
                    count=Count("pk"),
                )
                .values("year", "month", "count")
            )
            context["gazettes"] = self.group_gazettes(
                list(
                    self.model.objects.filter(
                        locality=locality, date__year=self.kwargs["year"]
                    )
                )
            )

        else:
            context["years"] = (
                self.model.objects.order_by("-date")
                .annotate(
                    year=ExtractYear("date"),
                    month=ExtractMonth("date"),
                    count=Count("pk"),
                )
                .values("year", "month", "count")
            )
            context["gazettes"] = self.group_gazettes(
                list(self.model.objects.filter(date__year=self.kwargs["year"]))
            )

        context["year"] = int(self.kwargs["year"])

        return self.render_to_response(context)

    def sort_gazettes(self, value):
        for g in value:
            return [g.title, g.date]

    def group_gazettes(self, gazettes):
        months = {m: [] for m in range(1, 13)}
        self.sort_gazettes(gazettes)
        for month, group in groupby(gazettes, key=lambda g: g.date.month):
            months[month] = list(group)

        # (month number, [list of gazettes]) tuples
        months = [(m, v) for m, v in months.items()]
        months.sort(key=lambda x: x[0])
        months = [(self.MONTHS[m - 1], v) for m, v in months]

        print(months)

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
        context["years"] = (
            self.model.objects.filter(locality=locality)
            .annotate(
                year=ExtractYear("date"), month=ExtractMonth("date"), count=Count("pk")
            )
            .values("year", "month", "count")
        )

        return self.render_to_response(context)
