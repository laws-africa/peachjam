from functools import cached_property
from math import ceil

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.text import gettext_lazy as _
from django.utils.text import slugify
from django.views.generic import TemplateView

from peachjam.helpers import lowercase_alphabet
from peachjam.models import (
    CauseList,
    Court,
    CourtClass,
    CourtDivision,
    CourtRegistry,
    DocumentNature,
    Judge,
    Taxonomy,
)
from peachjam.registry import registry
from peachjam.views import BaseDocumentDetailView, FilteredDocumentListView
from peachjam.views.courts import MonthMixin, RegistryMixin
from peachjam.views.generic_views import YearListMixin


@registry.register_doc_type("causelist")
class CauseListDetailView(BaseDocumentDetailView):
    model = CauseList
    template_name = "peachjam/causelist_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["judges"] = self.get_object().judges.values_list("name", flat=True)
        return context


class CauseListListView(TemplateView):
    template_name = "peachjam/causelist_list.html"
    navbar_link = "causelist"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # get only court classes and courts that have cause lists, and cache the result
        court_classes_with_cause_lists = cache.get_or_set(
            "court_classes_with_causelists",
            CourtClass.get_court_classes_with_cause_lists(),
        )
        context["court_classes"] = court_classes_with_cause_lists
        context["recent_causelists"] = (
            CauseList.objects.select_related("work")
            .prefetch_related("labels")
            .exclude(published=False)
            .order_by("-date")[:30]
        )
        self.add_entity_profile(context)
        context["doc_type"] = "CauseList"
        context["doc_count"] = CauseList.objects.filter(published=True).count()
        context["doc_count_noun"] = _("cause list")
        context["doc_count_noun_plural"] = _("cause lists")
        return context

    def add_entity_profile(self, context):
        pass


class FilteredCauseListView(FilteredDocumentListView):
    """Base List View class for filtering judgments."""

    model = CauseList
    navbar_link = "causelist"
    queryset = CauseList.objects.prefetch_related("judges", "labels").select_related(
        "work"
    )
    group_by_date = "month-year"
    exclude_facets = []

    def base_view_name(self):
        return _("CauseList")

    def get_form(self):
        self.form_defaults = {"sort": "-date"}
        return super().get_form()

    def page_title(self):
        return self.base_view_name()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["doc_type"] = "Judgment"
        context["page_title"] = self.page_title()
        context["doc_table_show_jurisdiction"] = False
        context["doc_count_noun"] = _("cause list")
        context["doc_count_noun_plural"] = _("cause lists")

        self.populate_years(context)
        context["documents"] = self.group_documents(context["documents"])

        return context

    def add_facets(self, context):
        context["facet_data"] = {}

        if "natures" not in self.exclude_facets:
            natures = DocumentNature.objects.filter(
                pk__in=self.form.filter_queryset(
                    self.get_base_queryset(), exclude="natures"
                )
                .order_by()
                .values_list("nature_id", flat=True)
                .distinct()
            )
            context["facet_data"]["natures"] = {
                "label": _("Document nature"),
                "type": "radio",
                "options": sorted(
                    [(n.code, n.name) for n in natures], key=lambda x: x[1]
                ),
                "values": self.request.GET.getlist("natures"),
            }

        if "divisions" not in self.exclude_facets:
            divisions = CourtDivision.objects.filter(
                pk__in=self.form.filter_queryset(
                    self.get_base_queryset(), exclude="divisions"
                )
                .order_by()
                .values_list("division_id", flat=True)
                .distinct()
            )

            context["facet_data"]["divisions"] = {
                "label": _("Court divisions"),
                "type": "checkbox",
                "options": sorted([(d.code, d.name) for d in divisions]),
                "values": self.request.GET.getlist("divisions"),
            }

        if "judges" not in self.exclude_facets:
            judges = list(
                judge
                for judge in self.form.filter_queryset(
                    self.get_base_queryset(), exclude="judges"
                )
                .order_by()
                .values_list("judges__name", flat=True)
                .distinct()
                if judge
            )
            context["facet_data"]["judges"] = {
                "label": Judge.model_label_plural,
                "type": "checkbox",
                "options": sorted([(j, j) for j in judges]),
                "values": self.request.GET.getlist("judges"),
            }

        if "taxonomy" not in self.exclude_facets:
            taxonomies = Taxonomy.objects.filter(
                pk__in=self.form.filter_queryset(
                    self.get_base_queryset(), exclude="taxonomies"
                )
                .filter(taxonomies__topic__isnull=False)
                .order_by("taxonomies__topic__id")
                .values_list("taxonomies__topic__id", flat=True)
                .distinct()
            )

            context["facet_data"]["taxonomies"] = {
                "label": _("Topics"),
                "type": "checkbox",
                "options": sorted(
                    [(t.slug, t.name) for t in taxonomies], key=lambda x: x[1]
                ),
                "values": self.request.GET.getlist("taxonomies"),
            }

        if "alphabet" not in self.exclude_facets:
            context["facet_data"]["alphabet"] = {
                "label": _("Alphabet"),
                "type": "radio",
                "options": [(a, a) for a in lowercase_alphabet()],
                "values": self.request.GET.get("alphabet"),
            }

    def populate_years(self, context):
        cache_key = f"causelist_years_{slugify(self.base_view_name())}"
        years = cache.get(cache_key)
        if years is None:
            years = self.get_base_queryset(exclude=["year", "month"]).dates(
                "date", "year", order="DESC"
            )
            cache.set(cache_key, years)
        context["years"] = years


class CauseListCourtDetailView(FilteredCauseListView):
    template_name = "peachjam/causelist_court_detail.html"

    @cached_property
    def court(self):
        return get_object_or_404(Court, code=self.kwargs["code"])

    def base_view_name(self):
        return f"{self.court.name} {_('Cause Lists')}"

    def get_base_queryset(self, exclude=None):
        qs = super().get_base_queryset(exclude=exclude).filter(court=self.court)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["court"] = self.court
        context["registry_label_plural"] = CourtRegistry.model_label_plural
        registries = self.court.registries.exclude(causelists__isnull=True)
        split_index = ceil(registries.count() / 2)
        for r in registries:
            r.get_absolute_url = reverse(
                "causelist_court_registry", args=[self.court.code, r.code]
            )

        context["registries"] = registries
        context["registry_groups"] = [
            registries[:split_index],
            registries[split_index:],
        ]
        context["all_years_url"] = reverse("causelist_court", args=[self.court.code])
        return context


class CauseListCourtYearView(YearListMixin, CauseListCourtDetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_months_url"] = reverse(
            "causelist_court_year", args=[self.court.code, self.year]
        )
        return context


class CauseListCourtMonthView(MonthMixin, CauseListCourtYearView):
    pass


class CauseListCourtRegistryDetailView(RegistryMixin, CauseListCourtDetailView):
    template_name = "peachjam/causelist_court_registry_detail.html"

    def base_view_name(self):
        return f'{super().base_view_name()} {_("Cause Lists")}'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_years_url"] = reverse(
            "causelist_court_registry", args=[self.court.code, self.registry.code]
        )
        return context


class CauseListCourtRegistryYearView(YearListMixin, CauseListCourtRegistryDetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_months_url"] = reverse(
            "causelist_court_registry_year",
            args=[self.court.code, self.registry.code, self.year],
        )
        return context


class CauseListCourtRegistryMonthView(MonthMixin, CauseListCourtRegistryYearView):
    pass


class CauseListCourtClassView(FilteredCauseListView):
    template_name = "peachjam/causelist_court_class_detail.html"

    def base_view_name(self):
        return f"{self.court_class.name} {_('Cause Lists')}"

    @cached_property
    def court_class(self):
        return get_object_or_404(CourtClass, slug=self.kwargs["court_class"])

    def get_base_queryset(self, exclude=None):
        qs = (
            super()
            .get_base_queryset(exclude=exclude)
            .filter(court__court_class=self.court_class)
        )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["court_class"] = self.court_class

        context["registries"] = Court.objects.filter(court_class=self.court_class)
        context["registry_label_plural"] = _("Courts")

        registries = Court.objects.filter(court_class=self.court_class).exclude(
            causelists__isnull=True
        )
        for r in registries:
            r.get_absolute_url = reverse("causelist_court", args=[r.code])

        context["registries"] = registries
        split_index = ceil(registries.count() / 2)
        context["registry_groups"] = [
            registries[:split_index],
            registries[split_index:],
        ]
        context["all_years_url"] = reverse(
            "causelist_court_class", args=[self.court_class.slug]
        )

        return context


class CauseListCourtClassYearView(YearListMixin, CauseListCourtClassView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_months_url"] = reverse(
            "causelist_court_class_year", args=[self.court_class.slug, self.year]
        )
        return context


class CauseListCourtClassMonthView(MonthMixin, CauseListCourtClassYearView):
    pass
