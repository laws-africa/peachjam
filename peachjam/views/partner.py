from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView

from peachjam.models import PartnerLogo


class PartnerLogoView(DetailView):
    model = PartnerLogo

    def get_object(self, queryset=None):
        return get_object_or_404(
            self.model,
            pk=self.kwargs["logo_pk"],
            partner__pk=self.kwargs["pk"],
        )

    def render_to_response(self, context, **response_kwargs):
        response = FileResponse(self.object.file, filename=self.object.filename)
        response["Cache-Control"] = "max-age=31536000"
        return response
