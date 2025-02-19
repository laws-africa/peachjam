from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from lawlibrary.constants import MUNICIPAL_CODES, PROVINCIAL_CODES
from liiweb.views import LocalityLegislationListView as BaseLocalityLegislationListView
from liiweb.views import LocalityLegislationView as BaseLocalityLegislationView
from peachjam.models import Locality


class LocalityLegislationView(BaseLocalityLegislationView):
    variant = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.variant == "provincial":
            context["locality_legislation_title"] = "Provincial Legislation"

        if self.variant == "municipal":
            context["locality_legislation_title"] = "Municipal By-laws"
            self.navbar_link = "legislation/municipal"

        return context

    def get_localities(self):
        if self.variant == "municipal":
            return Locality.objects.filter(code__in=MUNICIPAL_CODES)
        else:
            return Locality.objects.filter(code__in=PROVINCIAL_CODES)


class LocalityLegislationListView(BaseLocalityLegislationListView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.locality.code in PROVINCIAL_CODES:
            context["locality_legislation_title"] = "Provincial Legislation"
            context["show_subleg"] = True
            context["breadcrumb_link"] = reverse("locality_legislation")
        elif self.locality.code in MUNICIPAL_CODES:
            context["locality_legislation_title"] = "Municipal By-laws"
            context["doc_table_toggle"] = False
            context["page_heading"] = _(
                "%(locality)s By-laws" % {"locality": self.locality}
            )
            self.navbar_link = "legislation/municipal"
            context["breadcrumb_link"] = reverse("municipal_legislation")
            context["doc_table_citations"] = False
        else:
            context["locality_legislation_title"] = "Legislation"
            context["breadcrumb_link"] = reverse("legislation_list")
            context["doc_table_citations"] = False

        return context
