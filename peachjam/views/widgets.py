from django.http import Http404
from django.utils.translation import get_language
from django.views.generic import DetailView

from peachjam.helpers import add_slash
from peachjam.models import CoreDocument


class DocumentPopupView(DetailView):
    """Shows a popup with basic details for a document."""

    model = CoreDocument
    context_object_name = "document"
    template_name = "peachjam/document_popup.html"

    def get_object(self, *args, **kwargs):
        obj = self.model.objects.best_for_frbr_uri(
            add_slash(self.kwargs.get("frbr_uri")), get_language()
        )[0]
        if not obj:
            raise Http404()
        return obj
