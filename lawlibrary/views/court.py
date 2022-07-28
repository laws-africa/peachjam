from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from peachjam.models import Author, Judgment


class CourtDetailView(TemplateView):
    model = Author
    template_name = "lawlibrary/court_detail.html"

    def get_context_data(self, **kwargs):
        court = get_object_or_404(Author, code=self.kwargs["code"])

        context = super().get_context_data(**kwargs)

        judgments = Judgment.objects.filter(date__year=self.kwargs["year"])
        years = list(set(Judgment.objects.values_list("date__year", flat=True)))

        context["court"] = court
        context["judgments"] = judgments
        context["years"] = sorted(years, reverse=True)

        return context
