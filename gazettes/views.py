from django.core.cache import cache
from django.shortcuts import get_list_or_404
from django.views.generic import RedirectView, TemplateView

from gazettes.jurisdictions import (
    ALL_CONTRIBUTORS,
    COMMUNITIES,
    CONTRIBUTORS,
    JURISDICTION_MAP,
    jurisdiction_list,
)
from peachjam.models import Gazette
from peachjam.views import GazetteListView, GazetteYearView


class ArchiveView(RedirectView):
    def get_redirect_url(self, path, *args, **kwargs):
        return f"https://archive.gazettes.africa/archive/{path}"


class JurisdictionListView(TemplateView):
    template_name = "gazettes/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        jurisdictions = jurisdiction_list()
        context["country_jurisdictions"] = [
            x
            for x in jurisdictions
            if x.code not in COMMUNITIES and not x.parent_code and x.code != "aa"
        ]
        context["community_jurisdictions"] = [
            x for x in jurisdictions if x.code in COMMUNITIES
        ]
        context["num_gazettes"] = self.count_gazettes()
        context["contributors"] = ALL_CONTRIBUTORS
        return context

    def count_gazettes(self):
        count = cache.get("n_gazettes")
        if count is None:
            count = Gazette.objects.count()
            # cache for an hour
            cache.set("n_gazettes", count, 60 * 60)
        return count


class JurisdictionView(GazetteListView):
    def get(self, request, code, *args, **kwargs):
        self.jurisdiction = JURISDICTION_MAP[code]
        return super().get(request, code, *args, **kwargs)

    def get_localities(self, context):
        return self.jurisdiction.children

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["jurisdiction"] = self.jurisdiction
        context["contributors"] = CONTRIBUTORS.get(self.jurisdiction.code)
        return context


class YearView(GazetteYearView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["jurisdiction"] = juri = JURISDICTION_MAP[self.kwargs["code"]]
        context["contributors"] = CONTRIBUTORS.get(juri.code)
        return context


class OldGazetteView(RedirectView):
    """Redirect old URLs to the new peachjam URLs."""

    queryset = Gazette.objects

    def get_redirect_url(self, key, *args, **kwargs):
        # we don't have a unique index on key, so we have to get the first one
        gazette = get_list_or_404(self.queryset, key=key)[0]
        return gazette.get_absolute_url()
