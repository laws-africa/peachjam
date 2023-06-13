from django.shortcuts import get_object_or_404
from django.urls import reverse

from peachjam.helpers import lowercase_alphabet
from peachjam.models import Court, CourtRegistry, Judgment
from peachjam.views.generic_views import FilteredDocumentListView


class CourtDetailView(FilteredDocumentListView):
    """List View class for filtering a court's judgments.

    This view may be restricted to a specific year.
    """

    model = Judgment
    template_name = "peachjam/court_detail.html"
    navbar_link = "judgments"
    queryset = Judgment.objects.prefetch_related("judges")

    def get_base_queryset(self):
        qs = super().get_base_queryset().filter(court=self.court)
        if "year" in self.kwargs:
            qs = qs.filter(date__year=self.kwargs["year"])
        return qs

    def get_queryset(self):
        self.court = get_object_or_404(Court, code=self.kwargs["court_code"])
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        years = sorted(
            list(
                self.model.objects.filter(court=self.court)
                .order_by()
                .values_list("date__year", flat=True)
                .distinct()
            ),
            reverse=True,
        )

        context["years"] = [
            {"url": reverse("court_year", args=[self.court.code, y]), "year": y}
            for y in years
        ]

        context["all_years_url"] = reverse("court", args=[self.court.code])

        registries = list(
            registry
            for registry in self.court.registries.values("name", "code")
            if registry
        )

        context["registries"] = [
            {
                "url": reverse(
                    "court_registry", args=[self.court.code, registry["code"]]
                ),
                "registry": registry["name"],
            }
            for registry in registries
        ]

        context["all_registries_url"] = reverse("court", args=[self.court.code])

        judges = list(
            {
                judge
                for judge in self.form.filter_queryset(
                    self.get_base_queryset(), exclude="judges"
                ).values_list("judges__name", flat=True)
                if judge
            }
        )

        attorneys = list(
            {
                attorney
                for attorney in self.form.filter_queryset(
                    self.get_base_queryset(), exclude="attorneys"
                ).values_list("attorneys__name", flat=True)
                if attorney
            }
        )

        order_outcomes = list(
            {
                order_outcome
                for order_outcome in self.form.filter_queryset(
                    self.get_base_queryset(), exclude="order_outcomes"
                ).values_list("order_outcome__name", flat=True)
                if order_outcome
            }
        )

        context["court"] = self.court
        context["formatted_court_name"] = self.court.name
        if "year" in self.kwargs:
            context["year"] = self.kwargs["year"]
            context["formatted_court_name"] = (
                self.court.name + " - " + str(self.kwargs["year"])
            )

        context["facet_data"] = {
            "judges": judges,
            "alphabet": lowercase_alphabet(),
            "attorneys": attorneys,
            "order_outcomes": order_outcomes,
        }

        return context


class CourtYearView(CourtDetailView):
    queryset = Judgment.objects.prefetch_related("judges")


class CourtRegistryView(CourtDetailView):
    queryset = Judgment.objects.prefetch_related("judges")
    template_name = "peachjam/court_detail.html"

    def get_base_queryset(self):
        if "registry_code" in self.kwargs:
            self.registry = get_object_or_404(
                CourtRegistry, code=self.kwargs["registry_code"]
            )
        return super().get_base_queryset().filter(registry=self.registry)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["registry"] = self.registry
        context["formatted_court_name"] = self.registry
        return context


class CourtRegistryYearView(CourtRegistryView):
    queryset = Judgment.objects.prefetch_related("judges")
    template_name = "peachjam/court_detail.html"

    def get_base_queryset(self):
        qs = super().get_base_queryset().filter(registry=self.registry)
        if "year" in self.kwargs:
            qs = qs.filter(date__year=self.kwargs["year"])
        return qs
