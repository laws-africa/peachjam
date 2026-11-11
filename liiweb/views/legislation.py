import datetime
from collections import defaultdict
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from peachjam.helpers import chunks, get_language
from peachjam.models import (
    Glossary,
    JurisdictionProfile,
    Legislation,
    Locality,
    LocalityType,
    get_country_and_locality_or_404,
    pj_settings,
)
from peachjam.views import LegislationListView as BaseLegislationListView


def get_site_localities():
    """Return configured site localities that have published legislation."""
    settings = pj_settings()
    documents = Legislation.objects.filter(published=True, locality__isnull=False)
    if settings.default_document_jurisdiction_id:
        documents = documents.filter(
            jurisdiction=settings.default_document_jurisdiction_id
        )
    else:
        jurisdiction_ids = settings.document_jurisdictions.values_list("pk", flat=True)
        documents = documents.filter(jurisdiction_id__in=jurisdiction_ids)
    return Locality.objects.filter(
        pk__in=documents.order_by().values_list("locality_id", flat=True).distinct()
    )


class LegislationListView(BaseLegislationListView):
    template_name = "liiweb/legislation_list.html"
    variant = "current"
    latest_expression_only = True
    form_defaults = None
    national_only = True
    landing_page = True
    legislation_url_name = "legislation_list"
    variant_page_content = {
        "current": (
            _("Current legislation"),
            _("Principal legislation currently in force."),
        ),
        "recent": (
            _("Recent legislation"),
            _("Legislation published in the past year."),
        ),
        "subleg": (
            None,
            _("Regulations, rules and notices made under principal legislation."),
        ),
        "uncommenced": (
            _("Uncommenced legislation"),
            _("Legislation that is not yet in force."),
        ),
        "repealed": (
            _("Repealed legislation"),
            _("Legislation that is no longer in force."),
        ),
        "all": (
            _("All legislation"),
            _("Browse the complete legislation collection."),
        ),
    }

    @property
    def show_landing_page(self):
        return (
            self.landing_page
            and self.request.resolver_match.url_name == self.legislation_url_name
            and not self.request.htmx
            and not any(
                name in self.request.GET for name in self.form_class.base_fields
            )
        )

    def get_queryset(self):
        if self.show_landing_page:
            return self.get_model_queryset().none()
        return super().get_queryset()

    def get_paginate_by(self, queryset):
        if self.show_landing_page:
            return None
        return super().get_paginate_by(queryset)

    def get_template_names(self):
        if self.show_landing_page:
            return ["liiweb/legislation_landing.html"]
        return super().get_template_names()

    def get_form(self):
        self.form_defaults = {"sort": "title"}
        if self.variant in ["recent", "subleg"]:
            self.form_defaults = {"sort": "-date", "secondary_sort": "-frbr_uri_number"}
        return super().get_form()

    def get_model_queryset(self):
        legislation_content_type = ContentType.objects.get_for_model(
            self.model, for_concrete_model=False
        )
        return (
            super()
            .get_model_queryset()
            .filter(
                doc_type="legislation",
                polymorphic_ctype=legislation_content_type,
            )
        )

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
        context.update(self.get_legislation_presentation())
        if self.show_landing_page and self.national_only:
            localities = get_site_localities()
            context["locality_collections"] = [
                {
                    "title": locality_type.collection_title,
                    "url": locality_type.get_absolute_url(),
                }
                for locality_type in LocalityType.objects.filter(
                    localities__in=localities
                ).distinct()
            ]
            if localities.filter(locality_type__isnull=True).exists():
                context["locality_collections"].append(
                    {
                        "title": _("Local legislation"),
                        "url": reverse("locality_legislation") + "?type=",
                    }
                )
        elif self.national_only:
            page_heading, page_description = self.variant_page_content[self.variant]
            context["page_heading"] = page_heading or pj_settings().subleg_label
            context["page_description"] = page_description
        country = pj_settings().default_document_jurisdiction
        if country:
            place_code = country.iso.lower()
        else:
            place_code = None

        context["show_glossary"] = bool(
            place_code and Glossary.objects.filter(place_code=place_code).exists()
        )
        context["place_code"] = place_code

        if not self.show_landing_page:
            context["documents"] = self.group_documents(context["documents"])

        return context

    def get_legislation_presentation(self):
        """Supply shared landing-page links and terminology."""
        return {
            "landing_page_heading": _("Legislation"),
            "legislation_noun": _("legislation"),
            "show_document_nature": True,
            "show_subleg": True,
            "legislation_urls": {
                variant: reverse(
                    self.legislation_url_name + "_" + variant,
                    kwargs=self.get_legislation_url_kwargs(),
                )
                for variant in (
                    "current",
                    "all",
                    "recent",
                    "subsidiary",
                    "uncommenced",
                    "repealed",
                )
            },
        }

    def get_legislation_url_kwargs(self):
        return {}

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
            children_qs = self.get_model_queryset().filter(
                parent_work_id__in=parents,
                repealed=False,
                metadata_json__principal=True,
            )
            languages = self.form.cleaned_data.get("languages", [])
            if languages:
                children_qs = self.form.apply_filter_languages(children_qs)
            children_qs = children_qs.latest_expression()
            if not languages:
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
    locality_type_code = None
    extra_context = {"locality_legislation_title": _("Local legislation")}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        localities = self.get_localities()
        type_code = self.request.GET.get("type", self.locality_type_code)
        if type_code == "":
            localities = localities.filter(locality_type__isnull=True)
        elif type_code:
            locality_type = get_object_or_404(LocalityType, code=type_code)
            localities = localities.filter(locality_type=locality_type)
            context["locality_legislation_title"] = locality_type.collection_title
            context["locality_type"] = locality_type
        context["locality_groups"] = chunks(localities, 3)
        return context

    def get_localities(self):
        return get_site_localities()


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
    legislation_url_name = "locality_legislation_list"

    def get(self, *args, **kwargs):
        code = kwargs["code"]
        if "-" not in code:
            # redirect from <code> to <country>-<code>
            locality = get_object_or_404(Locality, code=code)
            return redirect("locality_legislation_list", code=locality.place_code())

        self.jurisdiction, self.locality = get_country_and_locality_or_404(code)
        return super().get(*args, **kwargs)

    def get_legislation_url_kwargs(self):
        return {"code": self.locality.place_code()}

    @property
    def show_document_nature(self):
        return (
            not self.locality.locality_type
            or self.locality.locality_type.show_document_nature
        )

    @property
    def show_subleg(self):
        return (
            not self.locality.locality_type
            or self.locality.locality_type.show_subsidiary_legislation
        )

    def get_form(self):
        form = super().get_form()
        if not self.show_document_nature:
            form.fields.pop("natures", None)
        return form

    def add_natures_facet(self, context):
        if self.show_document_nature:
            super().add_natures_facet(context)

    def add_children(self, queryset):
        if self.show_subleg:
            super().add_children(queryset)

    def get_base_queryset(self):
        return super().get_base_queryset().filter(locality=self.locality)

    def get_landing_page_queryset(self):
        return super().get_landing_page_queryset().filter(locality=self.locality)

    def get_variant_queryset(self, qs):
        if self.variant == "subleg" and not self.show_subleg:
            raise Http404()
        if self.variant == "current" and not self.show_subleg:
            return qs.filter(repealed=False)
        return super().get_variant_queryset(qs)

    def add_entity_profile(self, context):
        context["entity_profile"] = self.locality.entity_profile.first()
        context["entity_profile_title"] = self.locality.name

    def get_legislation_presentation(self):
        presentation = super().get_legislation_presentation()
        locality_type = self.locality.locality_type
        title = locality_type.legislation_title if locality_type else _("legislation")
        presentation.update(
            {
                "landing_page_heading": _("%(locality)s %(title)s")
                % {
                    "locality": self.locality,
                    "title": title,
                },
                "legislation_noun": title.lower(),
                "show_document_nature": self.show_document_nature,
                "show_subleg": self.show_subleg,
            }
        )
        return presentation

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        locality_type = self.locality.locality_type
        noun = context["legislation_noun"]
        context.update(
            {
                "locality": self.locality,
                "locality_legislation_title": locality_type.collection_title
                if locality_type
                else _("Local legislation"),
                "locality_collection_url": locality_type.get_absolute_url()
                if locality_type
                else reverse("locality_legislation") + "?type=",
                "locality_landing_url": reverse(
                    "locality_legislation_list", args=[self.locality.place_code()]
                ),
                "page_heading": context["landing_page_heading"],
                "doc_table_toggle": self.show_subleg,
                "place_code": self.locality.place_code(),
                "show_glossary": Glossary.objects.filter(
                    place_code=self.locality.place_code()
                ).exists(),
            }
        )
        if not self.show_landing_page:
            headings = {
                "current": _("Current %(legislation)s"),
                "all": _("All %(legislation)s"),
                "recent": _("Recent %(legislation)s"),
                "repealed": _("Repealed %(legislation)s"),
                "uncommenced": _("Uncommenced %(legislation)s"),
            }
            context["page_heading"] = (
                headings[self.variant] % {"legislation": noun}
                if self.variant in headings
                else pj_settings().subleg_label
            )
        context["entity_profile_title"] = context["page_heading"]
        profile = context.get("entity_profile")
        if profile and profile.background_photo:
            context["legislation_banner_url"] = profile.background_photo.url
        return context
