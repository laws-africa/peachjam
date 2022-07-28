from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, TemplateView

from peachjam.models import Author, Judgment


class CourtDetailView(DetailView):
    model = Author
    template_name = "lawlibrary/court_detail.html"

    def get_context_data(self, **kwargs):
        court = get_object_or_404(Author, pk=self.kwargs["pk"])
        context = super().get_context_data(**kwargs)

        judgments = Judgment.objects.filter(author=court)

        context["court"] = court
        context["judgments"] = judgments
        context["years"] = [
            2022,
            2021,
            2020,
            2020,
            2019,
            2018,
            2017,
            2016,
            2015,
            2014,
            2013,
            2012,
            2011,
            2010,
        ]
        return context


class FilteredListView(TemplateView):
    template_name = "lawlibrary/fake_filtered_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["years"] = [
            2022,
            2021,
            2020,
            2020,
            2019,
            2018,
            2017,
            2016,
            2015,
            2014,
            2013,
            2012,
            2011,
            2010,
        ]
        context["documents"] = Judgment.objects.order_by("-date")[:5]
        context["facet_data"] = {}
        context["facet_data"]["authors"] = ["Judge one", "Judge two", "Judge three"]
        context["facet_data"]["alphabet"] = ["A", "B", "C"]
        return context
