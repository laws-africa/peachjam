from django.shortcuts import get_object_or_404

from peachjam.models import Court, Judgment
from peachjam.utils import lowercase_alphabet
from peachjam.views.generic_views import FilteredDocumentListView


class CourtDetailView(FilteredDocumentListView):
    """List View class for filtering a court's judgments."""

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

        years = (
            self.model.objects.filter(court=self.court)
            .order_by("-date")
            .values_list("date__year", flat=True)
            .distinct()
        )

        judges = list(
            set(self.get_base_queryset().values_list("judges__name", flat=True))
        )
        if None in judges:
            judges.remove(None)

        context["court"] = self.court
        if "year" in self.kwargs:
            context["year"] = self.kwargs["year"]
        context["facet_data"] = {
            "judges": judges,
            "alphabet": lowercase_alphabet(),
            "years": list(years),
        }

        return context
