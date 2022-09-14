from collections import defaultdict

from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from peachjam.models import Legislation, Locality
from peachjam_api.serializers import LegislationSerializer


class LegislationListView(TemplateView):
    template_name = "lawlibrary/legislation_list.html"
    variant = "current"
    navbar_link = "legislation"

    def get_queryset(self):
        return (
            Legislation.objects.filter(locality=None)
            .distinct("work_frbr_uri")
            .order_by("work_frbr_uri", "-date")
            # don't load expensive, un-used fields
            .exclude(["content_html", "metadata_json"])
        )

    def filter_queryset(self, qs):
        if self.variant == "all":
            pass
        elif self.variant == "repealed":
            qs = qs.filter(repealed=True)
        elif self.variant == "current":
            qs = qs.filter(repealed=False, metadata_json__stub=False, parent_work=None)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = self.filter_queryset(self.get_queryset())
        qs = self.add_children(qs)

        context["legislation_table"] = LegislationSerializer(qs, many=True).data
        context["provinces"] = Locality.objects.filter(jurisdiction__iso="ZA")

        return context

    def add_children(self, queryset):
        # pull in children (subleg)
        parents = list({r.work_id for r in queryset.only("work_id")})

        children = defaultdict(list)
        children_qs = self.get_queryset().filter(
            parent_work_id__in=parents, repealed=False
        )
        # group children by parent
        for child in children_qs:
            children[child.parent_work_id].append(child)

        # fold in children
        qs = list(queryset)
        for parent in qs:
            parent.children = children.get(parent.work_id, [])
        return qs


class ProvincialLegislationListView(LegislationListView):
    model = Legislation
    template_name = "lawlibrary/provincial_legislation_list.html"

    def get(self, *args, **kwargs):
        self.locality = get_object_or_404(Locality, code=kwargs["code"])
        return super().get(*args, **kwargs)

    def get_queryset(self):
        return (
            Legislation.objects.filter(locality=self.locality)
            .distinct("work_frbr_uri")
            .order_by("work_frbr_uri", "-date")
        )

    def get_context_data(self, **kwargs):
        return super().get_context_data(locality=self.locality, **kwargs)
