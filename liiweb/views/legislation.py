from collections import defaultdict

from django.views.generic import TemplateView

from peachjam.models import Legislation
from peachjam.utils import get_language
from peachjam_api.serializers import LegislationSerializer


class LegislationListView(TemplateView):
    template_name = "liiweb/legislation_list.html"
    variant = "current"
    navbar_link = "legislation"
    model = Legislation

    def get_queryset(self):
        qs = self.model.objects.distinct("work_frbr_uri").order_by(
            "work_frbr_uri", "-date"
        )
        return qs.preferred_language(get_language(self.request))

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
        qs = qs.prefetch_related("taxonomies", "taxonomies__topic")
        qs = self.add_children(qs)

        context["legislation_table"] = LegislationSerializer(qs, many=True).data

        return context

    def add_children(self, queryset):
        # pull in children (subleg)
        parents = list(
            {r.work_id for r in queryset.only("work_id", "polymorphic_ctype_id")}
        )

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
