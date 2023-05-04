from peachjam.forms import BaseDocumentFilterForm


class ESDocumentFilterForm(BaseDocumentFilterForm):
    """Form for filtering documents in Elasticsearch. Only applies a subset of filters."""

    def filter_queryset(self, search, exclude=None):
        # TODO: filtering by letter or sorting by date requires changes to the indexing process
        # Order by date descending
        return search.sort("-date")
