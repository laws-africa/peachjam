from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.translation import get_language
from django.views.generic import DetailView, View
from languages_plus.models import Language

from peachjam.helpers import add_slash, add_slash_to_frbr_uri
from peachjam.models import CoreDocument, pj_settings
from peachjam.registry import registry


class DocumentDetailViewResolver(View):
    """Resolver view that returns detail views for documents based on their doc_type."""

    def dispatch(self, request, *args, **kwargs):
        # redirect /akn/foo/ to /akn/foo because FRBR URIs don't end in /
        if kwargs["frbr_uri"].endswith("/"):
            return redirect("document_detail", frbr_uri=kwargs["frbr_uri"][:-1])

        frbr_uri = add_slash(kwargs["frbr_uri"])
        obj, exact = self.get_document_for_frbr_uri(frbr_uri)

        if not obj:
            raise Http404()

        if not exact:
            return redirect(obj.get_absolute_url())

        view_class = registry.views.get(obj.doc_type)
        if view_class:
            view = view_class()
            view.setup(request, *args, **kwargs)

            return view.dispatch(request, *args, **kwargs)

    def get_document_for_frbr_uri(self, frbr_uri):
        obj = CoreDocument.objects.filter(expression_frbr_uri=frbr_uri).first()
        if obj:
            return obj, True

        # try looking based on the work URI instead, and use the latest expression
        qs = CoreDocument.objects.filter(work_frbr_uri=frbr_uri)

        # first, look for one in the user's preferred language
        lang = get_language()
        if lang:
            lang = Language.objects.filter(pk=lang).first()
            if lang:
                obj = qs.filter(language=lang).latest_expression().first()
                if obj:
                    return obj, False

        # try the default site language
        lang = pj_settings().default_document_language
        if lang:
            obj = qs.filter(language=lang).latest_expression().first()
            if obj:
                return obj, False

        # just get any one
        obj = qs.latest_expression().first()
        return obj, False


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class DocumentSourceView(DetailView):
    model = CoreDocument
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "frbr_uri"

    def render_to_response(self, context, **response_kwargs):
        if hasattr(self.object, "source_file") and self.object.source_file.file:
            source_file = self.object.source_file
            file = source_file.file.open()
            file_bytes = file.read()
            response = HttpResponse(file_bytes, content_type=source_file.mimetype)
            response[
                "Content-Disposition"
            ] = f"inline; filename={source_file.filename_for_download()}"
            response["Content-Length"] = str(len(file_bytes))
            return response
        raise Http404


class DocumentSourcePDFView(DocumentSourceView):
    def render_to_response(self, context, **response_kwargs):
        if hasattr(self.object, "source_file"):
            source_file = self.object.source_file
            file = source_file.as_pdf()

            # redirect search engine crawlers to the original source files
            # especially for gazettes
            if source_file.source_url:
                return redirect(source_file.source_url)

            return HttpResponse(file.read(), content_type="application/pdf")

        raise Http404()


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class DocumentMediaView(DetailView):
    """Serve an image file, such as

    /akn/za/judgment/afchpr/2022/1/eng@2022-09-14/media/tmpwx2063x2_html_31b3ed1b55e86754.png
    """

    model = CoreDocument
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "frbr_uri"

    def render_to_response(self, context, **response_kwargs):
        img = get_object_or_404(self.object.images, filename=self.kwargs["filename"])
        file = img.file.open()
        file_bytes = file.read()
        response = HttpResponse(file_bytes, content_type=img.mimetype)
        response["Content-Length"] = str(len(file_bytes))
        return response
