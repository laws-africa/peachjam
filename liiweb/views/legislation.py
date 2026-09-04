import datetime
from collections import defaultdict
from datetime import timedelta

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from peachjam.helpers import chunks, get_language
from peachjam.models import (
    Glossary,
    JurisdictionProfile,
    Locality,
    get_country_and_locality_or_404,
    pj_settings,
)
from peachjam.views import LegislationListView as BaseLegislationListView


class LegislationListView(BaseLegislationListView):
    template_name = "liiweb/legislation_list.html"
    variant = "current"
    latest_expression_only = True
    form_defaults = None
    national_only = True
    landing_page = True

    @property
    def show_landing_page(self):
        return (
            self.landing_page
            and self.national_only
            and self.request.resolver_match.url_name == "legislation_list"
        )

    def get_paginate_by(self, queryset):
        if self.show_landing_page:
            return 15
        return super().get_paginate_by(queryset)

    def get_template_names(self):
        if self.show_landing_page and not self.request.htmx:
            return ["liiweb/legislation_landing.html"]
        return super().get_template_names()

    def get_form(self):
        self.form_defaults = {"sort": "title"}
        if self.variant in ["recent", "subleg"]:
            self.form_defaults = {"sort": "-date", "secondary_sort": "-frbr_uri_number"}
        return super().get_form()

    def add_facets(self, context):
        if self.show_landing_page:
            context["facet_data"] = {}
        else:
            super().add_facets(context)

    def get_base_queryset(self, *args, **kwargs):
        qs = super().get_base_queryset(*args, **kwargs)
        if self.national_only:
            # only show national legislation, for the default country (if set)
            qs = qs.filter(locality=None)
            country = pj_settings().default_document_jurisdiction
            if country:
                qs = qs.filter(jurisdiction=country)
        qs = self.get_variant_queryset(qs)
        return qs

    def get_landing_page_queryset(self):
        qs = super().get_landing_page_queryset()
        if self.national_only:
            qs = qs.filter(locality=None)
            country = pj_settings().default_document_jurisdiction
            if country:
                qs = qs.filter(jurisdiction=country)
        return qs

    def get_variant_queryset(self, qs):
        if self.variant == "all":
            pass
        elif self.variant == "repealed":
            qs = qs.filter(repealed=True)
        elif self.variant == "current":
            qs = qs.filter(repealed=False, principal=True, parent_work=None)
        elif self.variant == "subleg":
            qs = qs.exclude(parent_work=None).filter(repealed=False, principal=True)
        elif self.variant == "uncommenced":
            qs = qs.filter(metadata_json__commenced=False)
        elif self.variant == "recent":
            qs = qs.filter(
                date__lte=datetime.date.today(),
                metadata_json__publication_date__gte=(
                    datetime.date.today() - timedelta(days=365)
                ).isoformat(),
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.show_landing_page:
            self.add_children(context["documents"])

        context["doc_table_toggle"] = True
        context["doc_table_toggle_title"] = pj_settings().subleg_label
        context["doc_table_citations"] = True
        context["doc_table_show_doc_type"] = False
        context["doc_table_show_court"] = False
        context["doc_table_show_author"] = False
        context["doc_table_show_jurisdiction"] = False
        settings = pj_settings()
        country = settings.default_document_jurisdiction
        if country is None and settings.document_jurisdictions.count() == 1:
            country = settings.document_jurisdictions.first()
        if country is None and self.national_only:
            countries = set(
                self.get_landing_page_queryset()
                .order_by()
                .values_list("jurisdiction__iso", flat=True)
                .distinct()
            )
            countries.discard(None)
            if len(countries) == 1:
                country = countries.pop()
        if country:
            place_code = (
                country.lower() if isinstance(country, str) else country.iso.lower()
            )
        else:
            glossary_place_codes = list(
                Glossary.objects.order_by()
                .values_list("place_code", flat=True)
                .distinct()[:2]
            )
            place_code = (
                glossary_place_codes[0] if len(glossary_place_codes) == 1 else None
            )

        context["show_glossary"] = bool(
            place_code and Glossary.objects.filter(place_code=place_code).exists()
        )
        context["place_code"] = place_code

        if not self.show_landing_page:
            context["documents"] = self.group_documents(context["documents"])

        return context

    def add_entity_profile(self, context):
        site_jurisdictions = pj_settings().document_jurisdictions.all()
        if site_jurisdictions.count() == 1:
            jurisdiction_profile = JurisdictionProfile.objects.filter(
                jurisdiction=site_jurisdictions.first()
            ).first()
            if jurisdiction_profile:
                context["entity_profile"] = jurisdiction_profile.entity_profile.first()
                context["entity_profile_title"] = jurisdiction_profile.jurisdiction.name

    def add_children(self, queryset):
        if self.variant != "all":
            # pull in children (subleg)
            parents = list(
                {
                    r.work_id
                    for r in queryset.prefetch_related()
                    .select_related()
                    .only("work_id", "polymorphic_ctype_id")
                }
            )

            children = defaultdict(list)
            children_qs = (
                self.get_model_queryset()
                .filter(
                    parent_work_id__in=parents,
                    repealed=False,
                    metadata_json__principal=True,
                )
                .latest_expression()
            )
            children_qs = children_qs.preferred_language(get_language(self.request))
            # group children by parent
            for child in children_qs:
                children[child.parent_work_id].append(child)

            # fold in children
            for parent in queryset:
                parent.children = children.get(parent.work_id, [])


class LocalityLegislationView(TemplateView):
    template_name = "liiweb/locality_legislation.html"
    navbar_link = "legislation/locality"
    extra_context = {"locality_legislation_title": "Local Legislation"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        localities = self.get_localities()
        if not localities:
            raise Http404()
        context["locality_groups"] = chunks(localities, 3)
        return context

    def get_localities(self):
        return Locality.objects.all()


class LocalityLegislationListView(LegislationListView):
    template_name = "liiweb/locality_legislation_list.html"
    navbar_link = "legislation/locality"
    extra_context = {
        "doc_table_show_date": False,
        "locality_legislation_title": LocalityLegislationView.extra_context[
            "locality_legislation_title"
        ],
    }
    national_only = False

    def get(self, *args, **kwargs):
        code = kwargs["code"]
        if "-" not in code:
            # redirect from <code> to <country>-<code>
            locality = get_object_or_404(Locality, code=code)
            return redirect("locality_legislation_list", code=locality.place_code())

        self.jurisdiction, self.locality = get_country_and_locality_or_404(code)
        return super().get(*args, **kwargs)

    def get_base_queryset(self):
        return super().get_base_queryset().filter(locality=self.locality)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["show_glossary"] = Glossary.objects.filter(
            place_code=self.kwargs["code"]
        ).exists()
        context["place_code"] = self.kwargs["code"]
        context.update(
            {
                "locality": self.locality,
                "page_heading": _("%(locality)s Legislation")
                % {"locality": self.locality},
                "entity_profile": self.locality.entity_profile.first(),
                "entity_profile_title": self.locality.name,
            }
        )
        return context
