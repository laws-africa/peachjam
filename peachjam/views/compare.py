import lxml.html
from django.http import Http404
from django.views.generic import TemplateView
from rest_framework.generics import get_object_or_404

from peachjam.models import CoreDocument


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
        doc_a_content = doc_a.get_or_create_document_content()
        doc_a_content.content_html = self.get_portion_html(doc_a, portion_a)
        doc_a_content.sync_document_html_cache()
        doc_b_content = doc_b.get_or_create_document_content()
        doc_b_content.content_html = self.get_portion_html(doc_b, portion_b)
        doc_b_content.sync_document_html_cache()

        if not doc_a_content.content_html or not doc_b_content.content_html:
            raise Http404()

        # root the primary document's TOC at portion-a
        doc_a_content.toc_json = [
            t for t in (doc_a_content.toc_json or []) if t["id"] == portion_a
        ]

        context["display_type"] = "html"

        return context

    def get_portion_html(self, doc, portion):
        try:
            doc_content = doc.document_content
        except doc.__class__.document_content.RelatedObjectDoesNotExist:
            return None
        if not doc_content.content_html:
            return None

        root = lxml.html.fromstring(doc_content.content_html)
        try:
            el = root.get_element_by_id(portion)
            return lxml.html.tostring(el, encoding="unicode")
        except KeyError:
            return None
