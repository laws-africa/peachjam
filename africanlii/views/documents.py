from django.http import FileResponse, Http404
from django.views.generic import DetailView

from peachjam.models import CoreDocument
from peachjam.views import AuthedViewMixin


class DocumentSourceView(AuthedViewMixin, DetailView):
    model = CoreDocument

    def render_to_response(self, context, **response_kwargs):
        if self.object.source_file and self.object.source_file.file:
            # TODO: ensure it's PDF
            return FileResponse(
                self.object.source_file.file.open(),
                filename=self.object.source_file.filename,
            )
        raise Http404
