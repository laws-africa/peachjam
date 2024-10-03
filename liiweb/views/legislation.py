import datetime
from collections import defaultdict
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from peachjam.helpers import chunks, get_language
from peachjam.models import JurisdictionProfile, Locality, pj_settings
from peachjam.views import LegislationListView as BaseLegislationListView


class LegislationListView(BaseLegislationListView):
    template_name = "liiweb/legislation_list.html"
    variant = "current"
    latest_expression_only = True
    form_defaults = None

    def get_form(self):
        self.form_defaults = {"sort": "title"}
        if self.variant in ["recent", "subleg"]:
            self.form_defaults = {"sort": "-date", "secondary_sort": "-frbr_uri_number"}
        return super().get_form()

    def get_base_queryset(self, *args, **kwargs):
        qs = super().get_base_queryset(*args, **kwargs)
        qs = self.get_variant_queryset(qs)
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
                metadata_json__publication_date__gte=(
                    datetime.date.today() - timedelta(days=365)
                ).isoformat()
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.add_children(context["documents"])

        context["doc_table_toggle"] = True
        context["doc_table_citations"] = True
        context["doc_table_show_doc_type"] = False
        context["doc_table_show_court"] = False
        context["doc_table_show_author"] = False
        context["doc_table_show_jurisdiction"] = False

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
        # pull in children (subleg)
        parents = list(
            {r.work_id for r in queryset.only("work_id", "polymorphic_ctype_id")}
        )

        children = defaultdict(list)
        children_qs = self.queryset.filter(
            parent_work_id__in=parents, repealed=False, metadata_json__principal=True
        ).latest_expression()
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        localities = Locality.objects.all()
        context["locality_groups"] = list(chunks(localities, 2))
        return context


class LocalityLegislationListView(LegislationListView):
    template_name = "liiweb/locality_legislation_list.html"
    navbar_link = "legislation/locality"

    def get(self, *args, **kwargs):
        self.locality = get_object_or_404(Locality, code=kwargs["code"])
        return super().get(*args, **kwargs)

    def get_base_queryset(self):
        return super().get_base_queryset().filter(locality=self.locality)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "locality": self.locality,
                "locality_legislation_title": "Provincial Legislation",
                "page_heading": _("%(locality)s Legislation")
                % {"locality": self.locality},
                "entity_profile": self.locality.entity_profile.first(),
                "entity_profile_title": self.locality.name,
            }
        )
        return context
