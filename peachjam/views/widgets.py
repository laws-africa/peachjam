import lxml.html
from cobalt.uri import FrbrUri
from django.http import Http404
from django.utils.translation import get_language
from django.views.generic import DetailView

from peachjam.helpers import add_slash, parse_utf8_html
from peachjam.models import CoreDocument


class DocumentPopupView(DetailView):
    """Shows a popup with basic details for a document."""

    model = CoreDocument
    context_object_name = "document"
    template_name = "peachjam/document_popup.html"

    def get_object(self, *args, **kwargs):
        try:
            frbr_uri = FrbrUri.parse(add_slash(self.kwargs["frbr_uri"]))
        except ValueError:
            raise Http404()

        self.portion = frbr_uri.portion
        frbr_uri.portion = None
        if frbr_uri.expression_date:
            uri = frbr_uri.expression_uri()
        else:
            uri = frbr_uri.work_uri()

        obj = self.model.objects.best_for_frbr_uri(uri, get_language())[0]
        if not obj:
            raise Http404()
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.portion:
            if not (self.object.content_html and self.object.content_html_is_akn):
                raise Http404()

            # try to find the portion within the object
            try:
                tree = parse_utf8_html(self.object.content_html)
                elems = tree.xpath(f'//*[@id="{self.portion}"]')
                if elems:
                    context["portion_html"] = lxml.html.tostring(
                        elems[0], encoding="unicode"
                    )
            except ValueError:
                raise Http404()

        return context
