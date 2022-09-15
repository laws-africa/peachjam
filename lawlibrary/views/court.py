from django.shortcuts import get_object_or_404

from lawlibrary.forms import CourtViewFilterForm
from peachjam.models import Author, Judgment
from peachjam.utils import lowercase_alphabet
from peachjam.views.generic_views import FilteredDocumentListView


class BaseCourtDetailView(FilteredDocumentListView):
    """Generic List View class for filtering a court's judgments."""

    model = Judgment
    template_name = "lawlibrary/court_detail.html"
    form_class = CourtViewFilterForm
    navbar_link = "judgments"

    def get_base_queryset(self):
        qs = super().get_base_queryset().filter(author=self.author)
        if "year" in self.kwargs:
            qs = qs.filter(date__year=self.kwargs["year"])
        return qs

    def get_queryset(self):
        self.author = get_object_or_404(Author, code=self.kwargs["code"])
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        years = (
            self.model.objects.filter(author=self.author)
            .order_by()
            .values_list("date__year", flat=True)
            .distinct()
        )

        context["years"] = sorted(years, reverse=True)

        judges = list(
            set(self.get_base_queryset().values_list("judges__name", flat=True))
        )
        if None in judges:
            judges.remove(None)

        context["court"] = self.author
        if "year" in self.kwargs:
            context["year"] = self.kwargs["year"]
        context["facet_data"] = {
            "judges": judges,
            "alphabet": lowercase_alphabet(),
        }

        return context


class CourtDetailView(BaseCourtDetailView):
    """View for listing a court's judgments."""

    pass


class CourtYearView(BaseCourtDetailView):
    """View for filtering a court's judgments, based on the year."""

    pass
