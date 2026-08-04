from functools import cached_property

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.dates import MONTHS
from django.utils.text import gettext_lazy as _

from peachjam.helpers import chunks
from peachjam.models import Court, CourtClass, CourtRegistry
from peachjam.views.generic_views import YearListMixin
from peachjam.views.judgment import FilteredJudgmentView


class CourtDetailView(FilteredJudgmentView):
    template_name = "peachjam/court_detail.html"

    @cached_property
    def court(self):
        if self.kwargs.get("code") == "all":
            return Court(name=_("All courts"), code="all")
        return get_object_or_404(Court, code=self.kwargs.get("code"))

    def base_view_name(self):
        return self.court.name

    def get_base_queryset(self, exclude=None):
        qs = super().get_base_queryset(exclude=exclude)
        if self.court.code != "all":
            qs = qs.filter(court=self.court)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["court"] = self.court
        context["registry_label_plural"] = CourtRegistry.model_label_plural
        if self.court.code != "all":
            context["registries"] = registries = self.court.registries.exclude(
                judgments__isnull=True
            )  # display registries with judgments only
            context["registry_groups"] = chunks(registries, 3)

        context["all_years_url"] = self.court.get_absolute_url()
        return context

    def add_courts_facet(self, context):
        if self.court.code == "all":
            super().add_courts_facet(context)

    def add_entity_profile(self, context):
        context["entity_profile"] = self.court.entity_profile.first()
        context["entity_profile_title"] = self.court.name


class CourtYearView(YearListMixin, CourtDetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_months_url"] = reverse(
            "court_year", args=[self.court.code, self.year]
        )
        return context


class MonthMixin:
    @property
    def month(self):
        if self.kwargs["month"] not in set(range(1, 13)):
            raise Http404("Invalid month")
        return self.kwargs["month"]

    def page_title(self):
        return f"{super().page_title()} {MONTHS[self.month]}"

    def get_base_queryset(self, exclude=None):
        if exclude is None:
            exclude = []
        qs = super().get_base_queryset(exclude=exclude)
        if "month" not in exclude:
            qs = qs.filter(date__month=self.month)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["month"] = MONTHS[self.month]
        return context


class CourtMonthView(MonthMixin, CourtYearView):
    pass


class RegistryMixin:
    template_name = "peachjam/court_registry_detail.html"

    def base_view_name(self):
        return self.registry.name

    @cached_property
    def registry(self):
        return get_object_or_404(CourtRegistry, code=self.kwargs.get("registry_code"))

    def get_base_queryset(self, *args, **kwargs):
        return super().get_base_queryset(*args, **kwargs).filter(registry=self.registry)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["registry"] = self.registry
        context["all_years_url"] = self.registry.get_absolute_url()
        return context


class CourtRegistryDetailView(RegistryMixin, CourtDetailView):
    pass


class CourtRegistryYearView(YearListMixin, CourtRegistryDetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_months_url"] = reverse(
            "court_registry_year", args=[self.court.code, self.registry.code, self.year]
        )
        return context


class CourtRegistryMonthView(MonthMixin, CourtRegistryYearView):
    pass


class CourtClassDetailView(FilteredJudgmentView):
    template_name = "peachjam/court_class_detail.html"

    def base_view_name(self):
        return self.court_class.name

    @cached_property
    def court_class(self):
        return get_object_or_404(CourtClass, slug=self.kwargs["court_class"])

    def get_base_queryset(self, exclude=None):
        return (
            super()
            .get_base_queryset(exclude=exclude)
            .filter(court__court_class=self.court_class)
        )

    def get_registries(self):
        return Court.objects.filter(court_class=self.court_class)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["court_class"] = self.court_class
        context["registries"] = self.get_registries()
        context["registry_label_plural"] = _("Courts")
        context["registry_groups"] = chunks(context["registries"], 3)
        context["all_years_url"] = self.court_class.get_absolute_url()

        return context

    def add_entity_profile(self, context):
        context["entity_profile"] = self.court_class.entity_profile.first()
        context["entity_profile_title"] = self.court_class.name


class CourtClassYearView(YearListMixin, CourtClassDetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_months_url"] = reverse(
            "court_class_year", args=[self.court_class.slug, self.year]
        )
        return context


class CourtClassMonthView(MonthMixin, CourtClassYearView):
    pass
