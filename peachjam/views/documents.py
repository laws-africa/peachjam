from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, View

from peachjam.models import CoreDocument
from peachjam.registry import registry
from peachjam.utils import add_slash, add_slash_to_frbr_uri


class DocumentDetailViewResolver(View):
    """Resolver view that returns detail views for documents based on their doc_type."""

    def dispatch(self, request, *args, **kwargs):
        # redirect /akn/foo/ to /akn/foo because FRBR URIs don't end in /
        if kwargs["frbr_uri"].endswith("/"):
            return redirect("document_detail", frbr_uri=kwargs["frbr_uri"][:-1])

        frbr_uri = add_slash(kwargs["frbr_uri"])
        obj = CoreDocument.objects.filter(expression_frbr_uri=frbr_uri).first()
        if not obj:
            # try looking based on the work URI instead, and use the latest expression
            # TODO: take the user's preferred language into account
            obj = (
                CoreDocument.objects.filter(work_frbr_uri=frbr_uri)
                .latest_expression()
                .first()
            )
            if obj:
                return redirect(obj.get_absolute_url())

        if not obj:
            raise Http404()

        view_class = registry.views.get(obj.doc_type)
        if view_class:
            view = view_class()
            view.setup(request, *args, **kwargs)

            return view.dispatch(request, *args, **kwargs)


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class DocumentSourceView(DetailView):
    model = CoreDocument
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "frbr_uri"

    def render_to_response(self, context, **response_kwargs):
        if hasattr(self.object, "source_file") and self.object.source_file.file:
            source_file = self.object.source_file
            file = source_file.file.open()
            bytes = file.read()
            response = HttpResponse(bytes, content_type=source_file.mimetype)
            response[
                "Content-Disposition"
            ] = f"inline; filename={source_file.filename_for_download()}"
            response["Content-Length"] = str(len(file_bytes))
            return response
        raise Http404


class DocumentSourcePDFView(DocumentSourceView):
    def render_to_response(self, context, **response_kwargs):
        if hasattr(self.object, "source_file"):
            file = self.object.source_file.as_pdf()
            return HttpResponse(file.read(), content_type="application/pdf")

        return Http404
