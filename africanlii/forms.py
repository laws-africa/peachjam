from peachjam.forms import BaseDocumentFilterForm


class ESDocumentFilterForm(BaseDocumentFilterForm):
    """Form for filtering documents in Elasticsearch. Only applies a subset of filters."""

    def filter_queryset(self, search, exclude=None):
        # Order by title then date descending
        search = search.sort("title_keyword", "-date")

        alphabet = self.cleaned_data.get("alphabet")
        if alphabet and exclude != "alphabet":
            search = search.filter(
                "prefix", title_keyword={"value": alphabet, "case_insensitive": True}
            )

        return search
