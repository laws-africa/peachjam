from django.views.generic import TemplateView

from peachjam.models import Locality


class GazetteListView(TemplateView):
    template_name = "lawlibrary/gazette_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        codes = "mp ec nc kzn gp wc lim nw fs".split()
        provinces = Locality.objects.filter(code__in=codes)
        groups = provinces[:5], provinces[5:]
        context["province_groups"] = groups
        context["num_gazettes"] = 10  # TODO: Replace filler number

        years = [
            2022,
            2021,
            2020,
            2009,
            2008,
            2001,
            1998,
            1999,
            1997,
            1996,
            1995,
            1993,
            1865,
            1901,
        ]  # TODO: Replace filler years
        context["years"] = years.sort(reverse=True)  # TODO: Replace filler years
        context["year_count"] = 100  # TODO: Replace filler year_count

        return context


class YearView(TemplateView):
    template_name = "lawlibrary/year.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        years = [
            2022,
            2021,
            2020,
            2009,
            2008,
            2001,
            1998,
            1999,
            1997,
            1996,
            1995,
            1993,
            1865,
            1901,
        ]  # TODO: Replace filler years
        context["years"] = sorted(years, reverse=True)  # TODO: Replace filler years

        return context
