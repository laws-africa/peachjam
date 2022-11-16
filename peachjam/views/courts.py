from django.shortcuts import get_object_or_404

from peachjam.models import Court, Judgment
from peachjam.utils import lowercase_alphabet
from peachjam.views.generic_views import FilteredDocumentListView


class CourtDetailView(FilteredDocumentListView):
    """List View class for filtering a court's judgments.

    This view may be restricted to a specific year.
    """

    model = Judgment
    template_name = "peachjam/court_detail.html"
    navbar_link = "judgments"

    def get_base_queryset(self):
        qs = super().get_base_queryset().filter(court=self.court)
        if "year" in self.kwargs:
            qs = qs.filter(date__year=self.kwargs["year"])
        return qs

    def get_queryset(self):
        self.court = get_object_or_404(Court, code=self.kwargs["code"])
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["years"] = sorted(
            list(
                self.model.objects.filter(court=self.court)
                .order_by()
                .values_list("date__year", flat=True)
                .distinct()
            ),
            reverse=True,
        )

        judges = list(
            self.get_base_queryset()
            .order_by("judges__name")
            .values_list("judges__name", flat=True)
            .distinct()
        )
        if None in judges:
            judges.remove(None)

        context["court"] = self.court
        context["formatted_court_name"] = self.court
        if "year" in self.kwargs:
            context["year"] = self.kwargs["year"]
            context["formatted_court_name"] = (
                self.court.name + " - " + self.kwargs["year"]
            )

        context["facet_data"] = {
            "judges": judges,
            "alphabet": lowercase_alphabet(),
        }

        return context


class CourtYearView(CourtDetailView):
    pass
