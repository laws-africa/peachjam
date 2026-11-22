from django.http import FileResponse, Http404
from django.views.generic import DetailView


class PublicImageView(DetailView):
    """Stream a public image through a stable URL suitable for cached pages.

    Templates, feeds, and metadata should reverse this view's named route instead
    of embedding a file field's .url: private S3/R2 storage URLs expire before the
    containing page may leave the cache. Streaming keeps bucket access on the
    server and works with both local and private remote storage.

    Configure a fixed field_name and a queryset enforcing public visibility.
    Protected document images must use the document media endpoint instead.
    """

    field_name = None

    def render_to_response(self, context, **response_kwargs):
        file = getattr(self.object, self.field_name)
        if not file:
            raise Http404
        return FileResponse(file.open("rb"))
