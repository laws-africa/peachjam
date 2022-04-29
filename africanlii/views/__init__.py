# flake8: noqa
from django.shortcuts import get_object_or_404
from django.views.generic import View

from africanlii.registry import registry
from peachjam.models import CoreDocument

from .common import *
from .documents import *
from .generic_document import *
from .judgment import *
from .legal_instrument import *
from .legislation import *


class DocumentDetailViewResolver(View):
    """Resolver view that returns detail views for documents based on their doc_type."""

    def dispatch(self, request, *args, **kwargs):
        obj = get_object_or_404(
            CoreDocument, expression_frbr_uri=kwargs.get("expression_frbr_uri")
        )

        view_class = registry.views.get(obj.doc_type)
        if view_class:
            view = view_class()
            view.slug_field = "expression_frbr_uri"
            view.slug_url_kwarg = "expression_frbr_uri"
            view.setup(request, *args, **kwargs)

            return view.dispatch(request, *args, **kwargs)
