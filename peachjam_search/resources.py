from peachjam.models import CoreDocument
from peachjam.resources import DownloadDocumentsResource


class SearchResultsDownloadResource(DownloadDocumentsResource):
    """Export local and remote documents returned by a search."""

    # Metadata required when a hit exists only in a federated search index.
    search_source_fields = [
        "authors",
        "citation",
        "commenced",
        "court",
        "date",
        "division",
        "expression_frbr_uri",
        "judges",
        "jurisdiction",
        "labels",
        "language",
        "locality",
        "nature",
        "principal",
        "registry",
        "repealed",
        "title",
    ]

    # Remote FakeDocuments contain raw Elasticsearch values rather than model
    # instances and related managers, so normalise both forms for export.
    def dehydrate_date(self, obj):
        return getattr(obj, "date", None)

    def dehydrate_source_url(self, obj):
        if not isinstance(obj, CoreDocument):
            return ""
        return super().dehydrate_source_url(obj)

    def dehydrate_court(self, obj):
        return self.render_related_value(getattr(obj, "court", None))

    def dehydrate_registry(self, obj):
        return self.render_related_value(getattr(obj, "registry", None))

    def dehydrate_division(self, obj):
        return self.render_related_value(getattr(obj, "division", None))

    def dehydrate_labels(self, obj):
        return self.render_related_values(getattr(obj, "labels", None))

    def dehydrate_judges(self, obj):
        return self.render_related_values(getattr(obj, "judges", None))

    def dehydrate_author(self, obj):
        return self.render_related_values(getattr(obj, "author", None))

    @staticmethod
    def render_related_value(value):
        return str(value) if value else ""

    @classmethod
    def render_related_values(cls, values):
        if not values:
            return ""
        if hasattr(values, "all"):
            values = values.all()
        if isinstance(values, str):
            return values
        return ", ".join(cls.render_related_value(value) for value in values)

    @classmethod
    def get_objects_for_download_by_frbr_uris(cls, frbr_uris):
        """Load local documents in the same order as the provided expression FRBR URIs."""
        documents = CoreDocument.objects.filter(
            expression_frbr_uri__in=frbr_uris
        ).values_list("expression_frbr_uri", "pk")
        pks_by_frbr_uri = dict(documents)
        pks = [pks_by_frbr_uri[uri] for uri in frbr_uris if uri in pks_by_frbr_uri]
        return cls.get_objects_for_download(pks)
