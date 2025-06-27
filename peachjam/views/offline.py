import os
from math import ceil

from django.conf import settings
from django.http.response import FileResponse, JsonResponse
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView

from peachjam.models import CoreDocument, Taxonomy
from peachjam.views import AllowedTaxonomyMixin, TaxonomyDetailView


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

        # n_docs should be based on the taxonomy and its children, but that's complicated
        # and the odds are the number of pages is very small
        n_docs = documents_qs.count()
        urls = self.get_urls(n_docs)

        data = {
            "name": self.taxonomy.name,
            "url": self.taxonomy.get_absolute_url(),
            "urls": urls,
            "documents": [
                # TODO: PDF urls if necessary
                {"url": doc.get_absolute_url(), "title": doc.title}
                for doc in documents_qs
            ],
        }
        return JsonResponse(data)

    def get_urls(self, n_docs):
        # urls to cache for the user to be able to browse for this topic
        n_pages = max(1, ceil(n_docs / TaxonomyDetailView.paginate_by))
        urls = []

        taxonomies = Taxonomy.objects.filter(pk__in=self.allowed_taxonomies["pk_list"])
        for taxonomy in taxonomies:
            taxonomy_url = taxonomy.get_absolute_url()
            urls.append(taxonomy_url)
            urls.extend(f"{taxonomy_url}?page={i}" for i in range(1, n_pages + 1))

        return urls
