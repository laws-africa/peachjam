from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from africanlii.forms import BaseDocumentFilterForm
from africanlii.utils import lowercase_alphabet
from peachjam.models import Author, Judgment


class CourtDetailView(TemplateView):
    model = Author
    template_name = "lawlibrary/court_detail.html"
    context_object_name = "documents"

    def get(self, request, *args, **kwargs):
        self.form = BaseDocumentFilterForm(request.GET)
        self.form.is_valid()

        return super(CourtDetailView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        court = get_object_or_404(Author, code=self.kwargs["code"])

        context = super().get_context_data(**kwargs)

        years = list(set(court.judgment_set.values_list("date__year", flat=True)))
        context["years"] = sorted(years, reverse=True)
        judges = list(set(court.judgment_set.values_list("judges__name", flat=True)))
        if None in judges:
            judges.remove(None)

        context["court"] = court
        context["judgments"] = court.judgment_set.all()
        context["facet_data"] = {
            "authors": judges,
            "years": years,
            "alphabet": lowercase_alphabet(),
        }

        return context


class YearView(TemplateView):
    template_name = "lawlibrary/court_detail.html"
    context_object_name = "documents"

    def get_context_data(self, **kwargs):
        court = get_object_or_404(Author, code=self.kwargs["code"])

        context = super().get_context_data(**kwargs)

        years = list(set(court.judgment_set.values_list("date__year", flat=True)))
        judges = list(set(court.judgment_set.values_list("judges__name", flat=True)))
        if None in judges:
            judges.remove(None)

        context["court"] = court
        context["judgments"] = Judgment.objects.filter(
            author=court, date__year=self.kwargs["year"]
        )

        context["years"] = sorted(years, reverse=True)
        context["facet_data"] = {
            "authors": judges,
            "years": years,
            "alphabet": lowercase_alphabet(),
        }

        return context
