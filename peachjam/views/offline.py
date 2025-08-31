import hashlib
from math import ceil

from django.contrib.staticfiles.finders import find as find_static
from django.http.response import FileResponse, JsonResponse
from django.urls.base import reverse
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView

from peachjam.models import CoreDocument, Taxonomy
from peachjam.views import AllowedTaxonomyMixin, TaxonomyDetailView


def service_worker(request):
    filepath = find_static("js/offline-service-worker.js")
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
    queryset = Taxonomy.objects.filter(allow_offline=True)

    def get_taxonomy(self):
        return self.get_object()

    def render_to_response(self, context, **response_kwargs):
        docs = list(
            CoreDocument.objects.filter(
                taxonomies__topic__in=self.allowed_taxonomies["pk_list"]
            )
            .distinct()
            .prefetch_related("images")
        )

        # n_docs should be based on the taxonomy and its children, but that's complicated
        # and the odds are the number of pages is very small
        urls = self.get_urls(docs)

        # hash of the documents and their timestamps
        fingerprint = sorted([(d.expression_frbr_uri, d.updated_at) for d in docs])
        fingerprint = hashlib.sha256(str(fingerprint).encode("utf-8")).hexdigest()

        data = {
            "name": self.taxonomy.name,
            "url": self.taxonomy.get_absolute_url(),
            "urls": urls,
            "fingerprint": fingerprint,
            "documents": [
                {"url": doc.get_absolute_url(), "title": doc.title} for doc in docs
            ],
        }
        return JsonResponse(data)

    def get_urls(self, docs):
        # urls to cache for the user to be able to browse for this topic
        n_docs = len(docs)
        n_pages = max(1, ceil(n_docs / TaxonomyDetailView.paginate_by))
        urls = []

        taxonomies = Taxonomy.objects.filter(pk__in=self.allowed_taxonomies["pk_list"])
        for taxonomy in taxonomies:
            taxonomy_url = taxonomy.get_absolute_url()
            urls.append(taxonomy_url)
            urls.extend(f"{taxonomy_url}?page={i}" for i in range(1, n_pages + 1))
            if taxonomy.is_root():
                # hack for top-level taxonomies which can appear at two URLs
                urls.append(
                    reverse(
                        "first_level_taxonomy_list", kwargs={"topic": taxonomy.slug}
                    )
                )

        # include document images
        for doc in docs:
            for image in doc.images.all():
                urls.append(doc.get_absolute_url() + "/media/" + image.filename)

            if not doc.content_html:
                # PDF
                urls.append(
                    reverse("document_source_pdf", args=[doc.expression_frbr_uri[1:]])
                )

        return urls
