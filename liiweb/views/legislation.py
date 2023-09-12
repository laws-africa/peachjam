from collections import defaultdict

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from peachjam.helpers import chunks, get_language
from peachjam.models import JurisdictionProfile, Legislation, Locality, pj_settings
from peachjam_api.serializers import LegislationSerializer


class LegislationListView(TemplateView):
    template_name = "liiweb/legislation_list.html"
    variant = "current"
    navbar_link = "legislation"
    model = Legislation

    def get_queryset(self):
        qs = (
            self.model.objects.distinct("work_frbr_uri")
            .order_by("work_frbr_uri", "-date", "language__pk")
            .preferred_language(get_language(self.request))
        )
        return qs

    def filter_queryset(self, qs):
        if self.variant == "all":
            pass
        elif self.variant == "repealed":
            qs = qs.filter(repealed=True)
        elif self.variant == "current":
            qs = qs.filter(
                repealed=False, metadata_json__principal=True, parent_work=None
            )
        elif self.variant == "subleg":
            qs = qs.exclude(parent_work=None).filter(
                repealed=False, metadata_json__principal=True
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = self.filter_queryset(self.get_queryset())
        qs = qs.prefetch_related("taxonomies", "taxonomies__topic", "work")
        qs = self.add_children(qs)

        context["legislation_table"] = LegislationSerializer(qs, many=True).data

        site_jurisdictions = pj_settings().document_jurisdictions.all()
        if site_jurisdictions.count() == 1:
            jurisdiction_profile = JurisdictionProfile.objects.filter(
                jurisdiction=site_jurisdictions.first()
            ).first()
            if jurisdiction_profile:
                context["entity_profile"] = jurisdiction_profile.entity_profile.first()
                context["entity_profile_title"] = jurisdiction_profile.jurisdiction.name

        return context

    def add_children(self, queryset):
        # pull in children (subleg)
        parents = list(
            {r.work_id for r in queryset.only("work_id", "polymorphic_ctype_id")}
        )

        children = defaultdict(list)
        children_qs = self.get_queryset().filter(
            parent_work_id__in=parents, repealed=False, metadata_json__principal=True
        )
        # group children by parent
        for child in children_qs:
            children[child.parent_work_id].append(child)

        # fold in children
        qs = list(queryset)
        for parent in qs:
            parent.children = children.get(parent.work_id, [])
        return qs


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

    def get_queryset(self):
        return super().get_queryset().filter(locality=self.locality)

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
