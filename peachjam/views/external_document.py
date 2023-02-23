from django.http import Http404
from django.shortcuts import redirect

from peachjam.models import ExternalDocument
from peachjam.registry import registry
from peachjam.views.generic_views import BaseDocumentDetailView


@registry.register_doc_type("external")
class ExternalDocumentView(BaseDocumentDetailView):
    model = ExternalDocument

    def get(self, *args, **kwargs):
        document = self.get_object(*args, **kwargs)
        if document.source_url:
            return redirect(document.source_url)
        raise Http404("Source url not found")
