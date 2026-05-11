from functools import cached_property

from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, TemplateView

from peachjam.models import ArbitralInstitution, ArbitrationAward, Court, Taxonomy
from peachjam.registry import registry
from peachjam.views.courts import FilteredJudgmentView
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)
from peachjam.views.judgment import JudgmentDetailView


class ArbitrationHubPage(TemplateView):
    template_name = "peachjam/arbitration/arbitration_hub.html"


class ArbitralInstitutionListView(ListView):
    template_name = "peachjam/arbitration/arbitral_institution_list.html"
    model = ArbitralInstitution
    context_object_name = "arbitral_institutions"


class ArbitralInstitutionDetailView(FilteredDocumentListView):
    template_name = "peachjam/arbitration/arbitral_institution_detail.html"
    model = ArbitrationAward
    navbar_link = "arbitration"

    @cached_property
    def arbitral_institution(self):
        return get_object_or_404(
            ArbitralInstitution,
            acronym=self.kwargs.get("acronym"),
        )

    def get_base_queryset(self, exclude=None):
        return (
            super()
            .get_base_queryset(exclude=exclude)
            .filter(institution=self.arbitral_institution)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["arbitral_institution"] = self.arbitral_institution
        context["entity_profile"] = self.arbitral_institution.entity_profile.first()
        context["entity_profile_title"] = self.arbitral_institution.name
        context["hide_follow_button"] = True
        return context


class ArbitrationAwardListView(FilteredDocumentListView):
    template_name = "peachjam/arbitration/arbitration_award_list.html"
    model = ArbitrationAward
    navbar_link = "arbitration"


class ArbitrationJudgmentTaxonomyMixin:
    arbitration_judgment_taxonomy_slug = "arbitration-judgment-categories"

    @cached_property
    def arbitration_judgment_taxonomy(self):
        return Taxonomy.objects.filter(
            slug=self.arbitration_judgment_taxonomy_slug
        ).first()

    def arbitration_judgment_taxonomy_filter(self):
        taxonomy = self.arbitration_judgment_taxonomy
        if not taxonomy:
            return None
        return {"taxonomies__topic__path__startswith": taxonomy.path}

    def get_arbitration_categories(self):
        taxonomy = self.arbitration_judgment_taxonomy
        if not taxonomy:
            return Taxonomy.objects.none()
        return Taxonomy.objects.filter(path__startswith=taxonomy.path).exclude(
            pk=taxonomy.pk
        )


class ArbitrationJudgmentListView(
    ArbitrationJudgmentTaxonomyMixin, FilteredJudgmentView
):
    template_name = "peachjam/arbitration/arbitration_judgment_list.html"
    navbar_link = "arbitration"

    def base_view_name(self):
        return _("Arbitration judgments")

    def get_base_queryset(self, exclude=None):
        qs = super().get_base_queryset(exclude=exclude)
        taxonomy_filter = self.arbitration_judgment_taxonomy_filter()
        if not taxonomy_filter:
            return qs.none()
        return qs.filter(**taxonomy_filter).distinct()

    def add_courts_facet(self, context):
        courts = Court.objects.filter(
            pk__in=self.form.filter_queryset(self.get_base_queryset(), exclude="courts")
            .order_by()
            .values_list("court_id", flat=True)
            .distinct()
        )
        if courts:
            context["facet_data"]["courts"] = {
                "label": _("Courts"),
                "type": "checkbox",
                "options": sorted([(court.name, court.name) for court in courts]),
                "values": self.request.GET.getlist("courts"),
            }

    def add_taxonomies_facet(self, context):
        categories = self.get_arbitration_categories().filter(
            pk__in=self.form.filter_queryset(
                self.get_base_queryset(), exclude="taxonomies"
            )
            .filter(taxonomies__topic__isnull=False)
            .order_by("taxonomies__topic__id")
            .values_list("taxonomies__topic__id", flat=True)
            .distinct()
        )
        if categories:
            context["facet_data"]["taxonomies"] = {
                "label": _("Categories"),
                "type": "checkbox",
                "options": sorted(
                    [(category.slug, category.name) for category in categories],
                    key=lambda item: item[1],
                ),
                "values": self.request.GET.getlist("taxonomies"),
            }

    def add_facets(self, context):
        context["facet_data"] = {}
        self.add_taxonomies_facet(context)
        self.add_courts_facet(context)
        self.add_years_facet(context)
        self.add_judges_facet(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["arbitration_categories"] = self.get_arbitration_categories()
        context["doc_table_show_jurisdiction"] = True

        for document in context["documents"]:
            if getattr(document, "is_group", False):
                continue
            document.listing_url = reverse(
                "arbitration_judgment_detail",
                kwargs={"frbr_uri": document.expression_frbr_uri[1:]},
            )

        return context


class ArbitrationJudgmentDetailView(
    ArbitrationJudgmentTaxonomyMixin, JudgmentDetailView
):
    template_name = "peachjam/arbitration/arbitration_judgment_detail.html"

    def get_queryset(self):
        qs = super().get_queryset()
        taxonomy_filter = self.arbitration_judgment_taxonomy_filter()
        if not taxonomy_filter:
            return qs.none()
        return qs.filter(**taxonomy_filter).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        taxonomy = self.arbitration_judgment_taxonomy
        context["is_arbitration_judgment"] = True
        context["arbitration_judgment_list_url"] = reverse("arbitration_judgment_list")
        context["arbitration_categories"] = sorted(
            [
                item.topic
                for item in self.object.taxonomies.all()
                if taxonomy
                and item.topic_id != taxonomy.pk
                and item.topic.path.startswith(taxonomy.path)
            ],
            key=lambda category: category.name,
        )
        return context


@registry.register_doc_type("arbitration_award")
class ArbitrationAwardDetailView(BaseDocumentDetailView):
    model = ArbitrationAward
    template_name = "peachjam/arbitration/arbitration_award_detail.html"
    queryset = ArbitrationAward.objects.select_related(
        "institution",
        "seat",
        "claimants_country_of_origin",
        "respondents_country_of_origin",
        "rules_of_arbitration",
    )
