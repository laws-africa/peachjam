from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, View

from africanlii.registry import registry
from peachjam.models import CoreDocument
from peachjam.views import AuthedViewMixin


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


class DocumentSourceView(AuthedViewMixin, DetailView):
    model = CoreDocument
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "expression_frbr_uri"

    def render_to_response(self, context, **response_kwargs):
        if self.object.source_file and self.object.source_file.file:
            # TODO: ensure it's PDF
            return FileResponse(
                self.object.source_file.file.open(),
                filename=self.object.source_file.filename,
            )
        raise Http404
