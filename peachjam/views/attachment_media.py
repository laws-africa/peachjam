from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from peachjam.models import CoreDocument, DocumentMedia


class DocumentResourceView:
    def initial(self, request, **kwargs):
        self.document = self.lookup_document()
        super().initial(request, **kwargs)

    def lookup_document(self):
        return get_object_or_404(CoreDocument, id=self.kwargs["document_id"])

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["document"] = self.document
        return context


class AttachmentMediaView(DocumentResourceView, APIView):
    def get(self, request, document_id, filename):
        document = get_object_or_404(CoreDocument, id=document_id)
        attachment = get_object_or_404(
            DocumentMedia, document=document, filename=filename
        )
        response = HttpResponse(
            attachment.file.read(), content_type=attachment.mime_type
        )
        response["Content-Disposition"] = f"inline; filename={attachment.filename}"
        response["Content-Length"] = str(attachment.size)
        return response
