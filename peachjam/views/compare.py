import lxml.html
from django.http import Http404
from django.views.generic import TemplateView
from rest_framework.generics import get_object_or_404

from peachjam.models import CoreDocument
from peachjam.xmlutils import parse_html_str


class ComparePortionsView(TemplateView):
    template_name = "peachjam/compare_portions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        frbr_uri_a = self.request.GET.get("uri-a")
        frbr_uri_b = self.request.GET.get("uri-b")
        portion_a = context["portion_a"] = self.request.GET.get("portion-a")
        portion_b = context["portion_b"] = self.request.GET.get("portion-b")
        if not frbr_uri_a or not frbr_uri_b or not portion_a or not portion_b:
            raise Http404()

        doc_a = context["doc_a"] = get_object_or_404(
            CoreDocument.objects, expression_frbr_uri=frbr_uri_a
        )
        doc_b = context["doc_b"] = get_object_or_404(
            CoreDocument.objects, expression_frbr_uri=frbr_uri_b
        )
        doc_a.content_html = self.get_portion_html(doc_a, portion_a)
        doc_b.content_html = self.get_portion_html(doc_b, portion_b)

        # root the primary document's TOC at portion-a
        doc_a.toc_json = [t for t in doc_a.toc_json if t["id"] == portion_a]

        context["display_type"] = "html"

        return context

    def get_portion_html(self, doc, portion):
        if doc.content_html:
            root = parse_html_str(doc.content_html)
            el = root.get_element_by_id(portion)
            if el is not None:
                return lxml.html.tostring(el, encoding="unicode")
