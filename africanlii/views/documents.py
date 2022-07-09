from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, TemplateView, View

from africanlii.registry import registry
from peachjam.models import CoreDocument


def view_attachment(attachment):
    response = HttpResponse(
        attachment.file.read(), content_type=attachment.instance.mimetype
    )
    response["Content-Disposition"] = f"inline; filename={attachment.instance.filename}"
    response["Content-Length"] = str(attachment.instance.file.size)
    return response


class HomePageView(TemplateView):
    template_name = "africanlii/home.html"


class DocumentDetailViewResolver(View):
    """Resolver view that returns detail views for documents based on their doc_type."""

    def dispatch(self, request, *args, **kwargs):
        obj = get_object_or_404(
            CoreDocument, expression_frbr_uri=kwargs.get("expression_frbr_uri")
        )

        view_class = registry.views.get(obj.doc_type)
        if view_class:
            view = view_class()
            view.setup(request, *args, **kwargs)

            return view.dispatch(request, *args, **kwargs)


class DocumentSourceView(DetailView):
    model = CoreDocument
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "expression_frbr_uri"

    def render_to_response(self, context, **response_kwargs):
        if hasattr(self.object, "source_file") and self.object.source_file.file:
            file = self.object.source_file.file.open()
            return view_attachment(file)
        raise Http404


class DocumentSourcePDFView(DocumentSourceView):
    def render_to_response(self, context, **response_kwargs):
        if hasattr(self.object, "source_file"):
            file = self.object.source_file.as_pdf()
            return HttpResponse(file.read(), content_type="application/pdf")

        return Http404
