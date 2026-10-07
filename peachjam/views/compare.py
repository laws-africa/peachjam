import json
from urllib.parse import urlencode

from cobalt.uri import FrbrUri
from django.apps import apps
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.views.generic import TemplateView
from lxml import etree
from rest_framework.generics import get_object_or_404

from peachjam.models import CoreDocument


class ComparePortion:
    def __init__(self, uri, document, portion_id, portion_title, portion_html):
        self.uri = uri
        self.document = document
        self.portion_id = portion_id
        self.portion_title = portion_title
        self.portion_html = portion_html
        self.content_html_is_akn = document.document_content.content_html_is_akn
        self.document_url = document.get_absolute_url()
        self.provision_url = f"{self.document_url}#{portion_id}"


class ComparePortionsView(TemplateView):
    template_name = "peachjam/compare/compare.html"

    def dispatch(self, request, *args, **kwargs):
        redirect_url = self.get_canonical_redirect_url()
        if redirect_url:
            return HttpResponseRedirect(redirect_url)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["uri_a"] = self.request.GET.get("uri-a", "")
        context["uri_b"] = self.request.GET.get("uri-b", "")
        context["column_a"] = self.get_column_context("a")
        context["column_b"] = self.get_column_context("b")
        return context

    def get_canonical_redirect_url(self):
        uri_a = self.request.GET.get("uri-a")
        uri_b = self.request.GET.get("uri-b")
        portion_a = self.request.GET.get("portion-a")
        portion_b = self.request.GET.get("portion-b")

        canonical_uri_a = self.get_canonical_uri(uri_a, portion_a)
        canonical_uri_b = self.get_canonical_uri(uri_b, portion_b)

        if not canonical_uri_a and canonical_uri_b:
            canonical_uri_a = canonical_uri_b
            canonical_uri_b = None

        needs_redirect = (
            bool(portion_a)
            or bool(portion_b)
            or canonical_uri_a != uri_a
            or canonical_uri_b != uri_b
        )
        if not needs_redirect:
            return None

        params = {}
        if canonical_uri_a:
            params["uri-a"] = canonical_uri_a
        if canonical_uri_b:
            params["uri-b"] = canonical_uri_b

        url = reverse("compare_portions")
        if params:
            url = f"{url}?{urlencode(params)}"
        return url

    def get_canonical_uri(self, uri, portion):
        if not uri:
            return None

        try:
            frbr_uri = FrbrUri.parse(uri)
        except ValueError:
            return uri

        if portion:
            frbr_uri.portion = portion
            return str(frbr_uri)

        if frbr_uri.portion:
            return str(frbr_uri)

        return uri

    def get_selected_portion(self, side):
        uri = self.request.GET.get(f"uri-{side}")
        if not uri:
            return None

        doc, portion_id = self.get_document_and_portion(uri)
        doc_content = doc.get_or_create_document_content()
        portion_html = self.get_portion_html(doc, portion_id)
        if not portion_html:
            raise Http404()

        return ComparePortion(
            uri=uri,
            document=doc,
            portion_id=portion_id,
            portion_title=doc_content.friendly_provision_title(portion_id),
            portion_html=portion_html,
        )

    def get_document_and_portion(self, uri):
        try:
            frbr_uri = FrbrUri.parse(uri)
        except ValueError as e:
            raise Http404() from e

        portion_id = frbr_uri.portion
        if not portion_id:
            raise Http404()

        frbr_uri.portion = None
        document = get_object_or_404(
            self.get_eligible_documents(), expression_frbr_uri=frbr_uri.expression_uri()
        )
        return document, portion_id

    def get_eligible_documents(self):
        return CoreDocument.objects.filter(
            published=True,
            document_content__content_html__isnull=False,
            document_content__toc_json__isnull=False,
        ).exclude(document_content__toc_json=[])

    def get_portion_html(self, doc, portion):
        doc_content = doc.get_or_create_document_content()
        if doc_content.content_html_is_akn:
            return doc.get_provision_by_eid(portion)

        elements = doc_content.content_html_tree.xpath(
            "//*[@id=$portion]", portion=portion
        )
        if elements:
            return etree.tostring(elements[0], encoding="unicode", method="html")
        return None

    def get_column_context(self, side, mode=None):
        selected_side = self.get_selected_portion(side)
        mode = mode or ("selected" if selected_side else "blank")
        chooser_params = self.get_chooser_params(side, mode, selected_side)
        return {
            "side": side,
            "mode": mode,
            "selected": selected_side,
            "uri_a": self.request.GET.get("uri-a", ""),
            "uri_b": self.request.GET.get("uri-b", ""),
            "compare_chooser_url": reverse("compare_chooser"),
            "chooser_params": chooser_params,
            "chooser_body_url": f"{reverse('compare_chooser')}?{urlencode(chooser_params)}",
        }

    def get_chooser_params(self, side, mode, selected_side):
        params = self.base_state_params()
        params.update(
            {
                "side": side,
                "fragment": "chooser",
            }
        )
        if mode in {"choose_document", "choose_provision"}:
            params["mode"] = mode
        if mode == "choose_provision":
            document_uri = self.request.GET.get("document-uri")
            if not document_uri and selected_side:
                document_uri = selected_side.document.expression_frbr_uri
            if document_uri:
                params["document-uri"] = document_uri
        return params

    def get_compare_url_for_portion(self, side, expression_frbr_uri, portion_id):
        frbr_uri = FrbrUri.parse(expression_frbr_uri)
        frbr_uri.portion = portion_id
        params = self.base_state_params()
        params[f"uri-{side}"] = str(frbr_uri)
        return f"{reverse('compare_portions')}?{urlencode(params)}"

    def base_state_params(self):
        params = {}
        for side in ("a", "b"):
            uri = self.request.GET.get(f"uri-{side}")
            if uri:
                params[f"uri-{side}"] = uri
        return params


class CompareChooserView(ComparePortionsView):
    template_name = "peachjam/compare/_column.html"

    def get_chooser_context(self, side):
        other_side = self.get_selected_portion("b" if side == "a" else "a")
        document_uri = self.request.GET.get("document-uri")
        q = (self.request.GET.get("q") or "").strip()
        selected_document = None
        toc_items = None
        toc_items_json = None
        suggested_provisions = []

        if document_uri:
            selected_document = get_object_or_404(
                self.get_eligible_documents(), expression_frbr_uri=document_uri
            )
            similar_provision_ids = self.get_similar_provision_ids(
                other_side, selected_document
            )
            suggested_provisions = self.get_similar_provision_choices(
                other_side, selected_document, side, limit=5
            )
            toc_items = self.decorate_toc_items(
                selected_document.get_or_create_document_content().toc_json or [],
                side,
                selected_document,
                similar_provision_ids,
            )
            toc_items_json = json.dumps(toc_items)

        return {
            "side": side,
            "uri_a": self.request.GET.get("uri-a", ""),
            "uri_b": self.request.GET.get("uri-b", ""),
            "compare_chooser_url": reverse("compare_chooser"),
            "other_side": other_side,
            "q": q,
            "selected_document": selected_document,
            "suggested_documents": (
                []
                if selected_document
                else self.get_suggested_documents(other_side, side)
            ),
            "search_results": (
                [] if selected_document else self.get_document_search_results(q, side)
            ),
            "suggested_provisions": (suggested_provisions if selected_document else []),
            "toc_items": toc_items,
            "toc_items_json": toc_items_json,
        }

    def get_document_search_results(self, q, side):
        if not q:
            return []
        return [
            self.document_choice(doc, side)
            for doc in self.get_candidate_documents(side)
            .latest_expression()
            .filter(title__icontains=q)
            .for_document_table()[:10]
        ]

    def get_candidate_documents(self, side):
        qs = self.get_eligible_documents()
        selected_side = self.get_selected_portion(side)
        other_side = self.get_selected_portion("b" if side == "a" else "a")
        comparison_side = selected_side or other_side
        if comparison_side:
            qs = qs.filter(frbr_uri_doctype=comparison_side.document.frbr_uri_doctype)
        return qs

    def get_suggested_documents(self, other_side, side):
        if not other_side or not apps.is_installed("peachjam_ml"):
            return []

        from peachjam_ml.models import DocumentEmbedding

        if not DocumentEmbedding.objects.filter(
            document=other_side.document, text_embedding__isnull=False
        ).exists():
            return []

        similar_documents = DocumentEmbedding.get_similar_documents(
            [other_side.document.pk], n_similar=5
        )
        doc_ids = [item["document_id"] for item in similar_documents]
        docs = {
            doc.pk: doc
            for doc in self.get_candidate_documents(side)
            .filter(pk__in=doc_ids)
            .select_related("work", "jurisdiction", "locality")
        }

        return [
            self.document_choice(
                docs[doc_id],
                side,
                suggested_provisions=self.get_similar_provision_choices(
                    other_side, docs[doc_id], side, limit=5
                ),
            )
            for doc_id in doc_ids
            if doc_id in docs
        ]

    def document_choice(self, document, side, suggested_provisions=None):
        params = self.base_state_params()
        params.update(
            {
                "side": side,
                "document-uri": document.expression_frbr_uri,
            }
        )
        return {
            "document": document,
            "chooser_url": f"{reverse('compare_chooser')}?{urlencode(params)}",
            "suggested_provisions": suggested_provisions or [],
        }

    def provision_choice(self, document, side, portion_id):
        return {
            "document": document,
            "portion_id": portion_id,
            "title": document.get_or_create_document_content().friendly_provision_title(
                portion_id
            ),
            "url": self.get_compare_url_for_portion(
                side, document.expression_frbr_uri, portion_id
            ),
        }

    def decorate_toc_items(self, toc_items, side, document, similar_provision_ids):
        return [
            self.decorate_toc_item(item, side, document, similar_provision_ids)
            for item in toc_items
        ]

    def decorate_toc_item(self, item, side, document, similar_provision_ids):
        item = dict(item)
        if item.get("id"):
            item["href"] = self.get_compare_url_for_portion(
                side, document.expression_frbr_uri, item["id"]
            )
            item["similar"] = item["id"] in similar_provision_ids
        else:
            item["href"] = None
            item["similar"] = False
        item["expanded"] = False
        item["children"] = self.decorate_toc_items(
            item.get("children") or [], side, document, similar_provision_ids
        )
        return item

    def get_similar_provision_ids(self, other_side, selected_document):
        return {
            choice["portion_id"]
            for choice in self.get_similar_provision_choices(
                other_side, selected_document, "a", limit=10
            )
        }

    def get_similar_provision_choices(
        self, other_side, selected_document, side, limit=5
    ):
        if not other_side or not apps.is_installed("peachjam_ml"):
            return []

        from peachjam_ml.models import ContentChunk

        provisions = ContentChunk.get_similar_provisions(
            other_side.document,
            other_side.portion_id,
            [selected_document],
            n_similar=limit,
        )
        return [
            self.provision_choice(selected_document, side, provision["portion"])
            for provision in provisions
        ]

    def dispatch(self, request, *args, **kwargs):
        return TemplateView.dispatch(self, request, *args, **kwargs)

    def get_template_names(self):
        if self.request.GET.get("search"):
            return ["peachjam/compare/_document_search_results.html"]
        if self.request.GET.get("fragment") == "chooser":
            return ["peachjam/compare/_chooser.html"]
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        side = self.request.GET.get("side")
        if side not in {"a", "b"}:
            raise Http404()

        if self.request.GET.get("search"):
            q = (self.request.GET.get("q") or "").strip()
            return {
                "side": side,
                "q": q,
                "search_results": self.get_document_search_results(q, side),
            }

        if self.request.GET.get("fragment") == "chooser":
            return self.get_chooser_context(side)

        if self.request.GET.get("cancel"):
            if not self.get_selected_portion(side):
                raise Http404()
            return self.get_column_context(side, "selected")

        mode = self.request.GET.get("mode")
        if mode not in {"choose_document", "choose_provision"}:
            mode = (
                "choose_provision"
                if self.request.GET.get("document-uri")
                else "choose_document"
            )
        return self.get_column_context(side, mode)
