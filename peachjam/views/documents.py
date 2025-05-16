import re

from cobalt import FrbrUri
from django.conf import settings
from django.http import Http404, HttpResponse
from django.http.response import FileResponse
from django.shortcuts import get_list_or_404, get_object_or_404, redirect, reverse
from django.utils.decorators import method_decorator
from django.utils.translation import get_language
from django.views.generic import DetailView, View

from peachjam.helpers import add_slash, add_slash_to_frbr_uri
from peachjam.helpers import get_language as get_language_from_request
from peachjam.models import (
    CoreDocument,
    DocumentNature,
    DocumentSocialImage,
    ExtractedCitation,
)
from peachjam.registry import registry
from peachjam.resolver import resolver
from peachjam.views import BaseDocumentDetailView


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class DocumentDetailView(DetailView):
    """Base class for document-based detail views that enforces permissions."""

    model = CoreDocument
    queryset = CoreDocument.objects.filter(published=True)
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "frbr_uri"
    context_object_name = "document"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.restricted:
            perm = f"{obj._meta.app_label}.view_{obj._meta.model_name}"
            if not self.request.user.has_perm(perm, obj):
                raise Http404()
        return obj


class DocumentDetailViewResolver(View):
    """Resolver view that returns detail views for documents based on their doc_type."""

    def dispatch(self, request, *args, **kwargs):
        # redirect /akn/foo/ to /akn/foo because FRBR URIs don't end in /
        if kwargs["frbr_uri"].endswith("/"):
            return redirect("document_detail", frbr_uri=kwargs["frbr_uri"][:-1])

        frbr_uri = add_slash(kwargs["frbr_uri"])

        try:
            # return 404 early if frbr_uri is invalid
            parsed_frbr_uri = FrbrUri.parse(frbr_uri)
        except ValueError:
            raise Http404()

        # ensure portion is ignored when looking for a document
        portion = parsed_frbr_uri.portion
        parsed_frbr_uri.portion = None
        uri_to_search = (
            parsed_frbr_uri.expression_uri()
            if parsed_frbr_uri.expression_date
            else parsed_frbr_uri.work_uri()
        )
        obj, exact = CoreDocument.objects.best_for_frbr_uri(
            uri_to_search, get_language()
        )

        if not obj:
            url = resolver.get_url_for_frbr_uri(parsed_frbr_uri, frbr_uri)
            if url:
                return redirect(url)
            raise Http404()

        if not obj.published:
            raise Http404()

        if not exact or portion:
            url = obj.get_absolute_url()
            # this translates from /akn/.../~sec_2 to /akn/.../#sec_2
            if portion:
                url = url + "#" + portion
            return redirect(url)

        if obj.restricted:
            restricted_view = RestrictedDocument403View()
            restricted_view.setup(request, *args, **kwargs)
            perm = f"{obj._meta.app_label}.view_{obj._meta.model_name}"
            if not request.user.has_perm(perm, obj):
                return restricted_view.dispatch(request, *args, **kwargs)

        view_class = registry.views.get(obj.doc_type)

        if view_class:
            view = view_class()
            view.setup(request, *args, **kwargs)

            return view.dispatch(request, *args, **kwargs)

        raise Exception(
            f"The document type {obj.doc_type} does not have a view registered."
        )


class DocumentSourceView(DocumentDetailView):
    """Returns the source file (non-PDF) for a document. If the source file is a PDF, it redirects to the PDF view."""

    def render_to_response(self, context, **response_kwargs):
        if hasattr(self.object, "source_file"):
            source_file = self.object.source_file
            anonymised = getattr(self.object, "anonymised", False)

            # redirect to the PDF view if necessary
            if (
                source_file.file
                and source_file.mimetype == "application/pdf"
                or anonymised
                and source_file.anonymised_file_as_pdf
            ):
                return redirect(
                    reverse(
                        "document_source_pdf",
                        kwargs={"frbr_uri": self.object.expression_frbr_uri[1:]},
                    )
                )

            if source_file.file and (not anonymised or source_file.file_is_anonymised):
                if source_file.source_url:
                    return redirect(source_file.source_url)

                if getattr(source_file.file.storage, "custom_domain", None):
                    # use the storage's custom domain to serve the file
                    return redirect(source_file.file.url)

                return self.make_response(
                    source_file.file.open(),
                    source_file.mimetype,
                    source_file.filename_for_download(),
                )

        raise Http404

    def make_response(self, f, content_type, fname):
        file_bytes = f.read()
        response = HttpResponse(file_bytes, content_type=content_type)
        response["Content-Disposition"] = f"attachment; filename={fname}"
        response["Content-Length"] = str(len(file_bytes))
        return response


class DocumentSourcePDFView(DocumentSourceView):
    """Returns the PDF source file for a document. For anonymised judgments, we return an anonymised version if
    available."""

    def render_to_response(self, context, **response_kwargs):
        if hasattr(self.object, "source_file"):
            source_file = self.object.source_file

            # if the source file is remote and a pdf, just redirect there
            if source_file.source_url and source_file.mimetype == "application/pdf":
                return redirect(source_file.source_url)

            pdf = source_file.as_pdf()

            # special case for anonymised judgments: use the anonymised file if available
            if (
                getattr(self.object, "anonymised", False)
                and not source_file.file_is_anonymised
            ):
                # this may be None
                pdf = source_file.anonymised_file_as_pdf

            if pdf:
                if getattr(pdf.storage, "custom_domain", None):
                    # use the storage's custom domain to serve the file
                    return redirect(pdf.url)
                else:
                    return self.make_response(
                        pdf,
                        "application/pdf",
                        source_file.filename_for_download(".pdf"),
                    )

        raise Http404()


class DocumentPublicationView(DocumentSourceView):
    def render_to_response(self, context, **response_kwargs):
        if hasattr(self.object, "publication_file"):
            publication_file = self.object.publication_file
            if publication_file.use_source_file:
                return redirect(
                    reverse(
                        "document_source",
                        kwargs={"frbr_uri": self.object.expression_frbr_uri[1:]},
                    )
                )
            if publication_file.url:
                return redirect(publication_file.url)

            return self.make_response(
                publication_file.file.open(),
                publication_file.mimetype,
                publication_file.filename,
            )
        raise Http404


class DocumentMediaView(DocumentDetailView):
    """Serve an image file, such as

    /akn/za/judgment/afchpr/2022/1/eng@2022-09-14/media/tmpwx2063x2_html_31b3ed1b55e86754.png
    """

    def render_to_response(self, context, **response_kwargs):
        # there should only be one, but until we enforce uniqueness of filenames, get the first in the list
        # see https://github.com/laws-africa/peachjam/issues/2024
        img = get_list_or_404(self.object.images, filename=self.kwargs["filename"])[0]

        if getattr(img.file.storage, "custom_domain", None):
            # use the storage's custom domain to serve the file
            return redirect(img.file.url)

        file = img.file.open()
        file_bytes = file.read()
        response = HttpResponse(file_bytes, content_type=img.mimetype)
        response["Content-Length"] = str(len(file_bytes))
        return response


class DocumentAttachmentView(DocumentDetailView):
    def render_to_response(self, context, **response_kwargs):
        file = self.object.attachedfiles_set.filter(
            filename=self.kwargs["filename"]
        ).first()
        if file and not file.private:
            if getattr(file.file.storage, "custom_domain", None):
                # use the storage's custom domain to serve the file
                return redirect(file.file.url)

            file_bytes = file.file.open().read()
            response = HttpResponse(file_bytes, content_type=file.mimetype)
            filename = re.sub(r"[^A-Za-z0-9._-]", "", file.filename)
            response["Content-Disposition"] = f"attachment; filename={filename}"
            response["Content-Length"] = str(len(file_bytes))
            return response
        raise Http404


class DocumentCitationsView(DocumentDetailView):
    template_name = "peachjam/document/_citations_list_more.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        direction = self.request.GET.get("direction", "incoming")

        try:
            nature = int(self.request.GET.get("nature"))
            nature = get_object_or_404(DocumentNature, pk=nature)
        except (TypeError, ValueError):
            raise Http404

        try:
            offset = max(0, int(self.request.GET.get("offset", 0)))
        except ValueError:
            raise Http404

        doc = self.get_object()
        works = (
            doc.work.works_citing_current_work()
            if direction == "incoming"
            else doc.work.cited_works()
        )

        (
            context["docs"],
            context["truncated"],
        ) = ExtractedCitation.fetch_grouped_citation_docs(
            works,
            get_language_from_request(self.request),
            nature=nature,
            offset=offset,
        )
        context["start"] = offset
        context["offset"] = offset + len(context["docs"])
        context["nature"] = nature
        context["direction"] = direction
        context["doc_table_id"] = f"citations-table-{direction}-{nature.pk}"

        return context


class RestrictedDocument403View(BaseDocumentDetailView):
    """The view used when a user tries to access a restricted document without permission."""

    model = CoreDocument
    template_name = "peachjam/restricted_document_detail.html"

    def get_context_data(self, **kwargs):
        # deliberately don't call super
        context = {}
        context.update(kwargs)
        context["document"] = self.get_object()
        return context

    def render_to_response(self, context, **response_kwargs):
        return super().render_to_response(context, status=403, **response_kwargs)


class DocumentSocialImageView(DocumentDetailView):
    """Image for this document used by social media."""

    def get(self, request, *args, **kwargs):
        document = self.get_object()
        debug = settings.DEBUG and "debug" in request.GET
        html_str = DocumentSocialImage.html_for_document(document, debug)

        if debug:
            return HttpResponse(html_str)

        image = DocumentSocialImage.get_or_create_for_document(document, html_str)
        if getattr(image.file.storage, "custom_domain", None):
            # use the storage's custom domain to serve the file
            return redirect(image.file.url)

        return FileResponse(image.file, content_type="image/png")
