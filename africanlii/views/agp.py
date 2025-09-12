from django.views.generic import TemplateView

from peachjam.views import DocumentListView


class AGPSoftLawListView(DocumentListView):
    template_name = "peachjam/soft_law_list.html"
    navbar_link = "soft_law"

    def get_base_queryset(self):
        return super().get_base_queryset().exclude(frbr_uri_doctype="doc")


class AGPReportsGuidesListView(DocumentListView):
    template_name = "peachjam/reports_guides_list.html"
    navbar_link = "reports_guides"
    form_defaults = {"sort": "title"}

    def get_base_queryset(self):
        return super().get_base_queryset().filter(frbr_uri_doctype="doc")


class AGPMOOCView(TemplateView):
    template_name = "africanlii/mooc.html"
