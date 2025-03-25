from cobalt import FrbrUri
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.http import Http404, HttpResponse
from django.http.response import FileResponse
from django.shortcuts import get_list_or_404, get_object_or_404, redirect, reverse
from django.utils.decorators import method_decorator
from django.utils.translation import get_language
from django.views.generic import DetailView, View
from guardian.shortcuts import get_groups_with_perms

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

            if not request.user.is_authenticated:
                return restricted_view.dispatch(request, *args, **kwargs)

            if not request.user.is_superuser or not request.user.is_staff:
                # check if user belongs to a group that has access to the document
                doc_groups = get_groups_with_perms(obj)
                user_groups = request.user.groups.all()
                if not doc_groups.intersection(user_groups):
                    return restricted_view.dispatch(request, *args, **kwargs)

        view_class = registry.views.get(obj.doc_type)

        if view_class:
            view = view_class()
            view.setup(request, *args, **kwargs)

            return view.dispatch(request, *args, **kwargs)

        raise Exception(
            f"The document type {obj.doc_type} does not have a view registered."
        )


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class DocumentSourceView(DetailView):
    model = CoreDocument
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "frbr_uri"

    def render_to_response(self, context, **response_kwargs):
        if hasattr(self.object, "source_file") and self.object.source_file.file:
            source_file = self.object.source_file

            if source_file.mimetype == "application/pdf":
                # If the source file is a PDF, redirect to the source.pdf URL
                # This avoids providing an identical file from two different URLs, which is bad for caching,
                # bad for Google, and bad for PocketLaw.
                return redirect(
                    reverse(
                        "document_source_pdf",
                        kwargs={"frbr_uri": self.object.expression_frbr_uri[1:]},
                    )
                )

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
    def render_to_response(self, context, **response_kwargs):
        if hasattr(self.object, "source_file"):
            source_file = self.object.source_file

            # if the source file is remote and a pdf, just redirect there
            if source_file.source_url and source_file.mimetype == "application/pdf":
                return redirect(source_file.source_url)

            pdf = source_file.as_pdf()
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


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class DocumentMediaView(DetailView):
    """Serve an image file, such as

    /akn/za/judgment/afchpr/2022/1/eng@2022-09-14/media/tmpwx2063x2_html_31b3ed1b55e86754.png
    """

    model = CoreDocument
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "frbr_uri"

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


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class DocumentCitationsView(DetailView):
    model = CoreDocument
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "frbr_uri"
    context_object_name = "document"
    template_name = "peachjam/_citations_list_items.html"

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


@method_decorator(add_slash_to_frbr_uri(), name="setup")
class DocumentSocialImageView(DetailView):
    """Image for this document used by social media."""

    model = CoreDocument
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "frbr_uri"
    context_object_name = "document"

    def get(self, request, *args, **kwargs):
        document = self.get_object()
        site = get_current_site(request)
        debug = settings.DEBUG and "debug" in request.GET
        html_str = DocumentSocialImage.html_for_document(document, site, debug)

        if debug:
            return HttpResponse(html_str)

        image = DocumentSocialImage.get_or_create_for_document(document, html_str)
        if getattr(image.file.storage, "custom_domain", None):
            # use the storage's custom domain to serve the file
            return redirect(image.file.url)

        return FileResponse(image.file, content_type="image/png")
