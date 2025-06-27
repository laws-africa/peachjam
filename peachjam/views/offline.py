import os

from django.conf import settings
from django.http.response import FileResponse, JsonResponse
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView

from peachjam.models import CoreDocument, Taxonomy
from peachjam.views import AllowedTaxonomyMixin


def service_worker(request):
    filepath = os.path.join(
        settings.BASE_DIR, "peachjam/static/js/offline-service-worker.js"
    )
    response = FileResponse(open(filepath, "rb"), content_type="application/javascript")
    response["Cache-Control"] = "no-cache"
    return response


class OfflineHomeView(TemplateView):
    template_name = "peachjam/offline/home.html"


class OfflineView(TemplateView):
    template_name = "peachjam/offline/offline.html"


class TaxonomyManifestView(AllowedTaxonomyMixin, DetailView):
    """This view tells the offline system what pages need to be cached for this taxonomy topic. This includes
    the documents in the topic (and its children), and the pages for browsing the topic."""

    model = Taxonomy

    def get_taxonomy(self):
        # TODO: work with the root offline topic if this is a descendant
        return self.get_object()

    def render_to_response(self, context, **response_kwargs):
        documents_qs = (
            CoreDocument.objects.filter(
                taxonomies__topic__in=self.allowed_taxonomies["pk_list"]
            )
            .distinct()
            .only("title", "expression_frbr_uri")
        )

        # TODO: assets

        data = {
            "name": self.taxonomy.name,
            "url": self.taxonomy.get_absolute_url(),
            "assets": [],
            "documents": [
                {"url": doc.get_absolute_url(), "title": doc.title}
                for doc in documents_qs
            ],
        }
        return JsonResponse(data)
