from peachjam.forms import BaseDocumentFilterForm


class ESDocumentFilterForm(BaseDocumentFilterForm):
    """Form for filtering documents in Elasticsearch. Only applies a subset of filters."""

    def filter_queryset(self, search, exclude=None):
        alphabet = self.cleaned_data.get("alphabet")
        jurisdictions = self.params.getlist("jurisdictions")
        years = self.params.getlist("years")
        if not isinstance(exclude, list):
            exclude = [exclude]

        # Order by title then date descending
        search = search.sort("title_keyword", "-date")

        if alphabet and "alphabet" not in exclude:
            search = search.filter(
                "prefix", title_keyword={"value": alphabet, "case_insensitive": True}
            )

        if jurisdictions and "jurisdictions" not in exclude:
            search = search.filter("terms", jurisdiction=jurisdictions)

        if years and "years" not in exclude:
            search = search.filter("terms", year=years)

        return search

    def filter_faceted_search(self, search):
        """Add filters to a faceted search object, which is a bit different to adding them to the normal search
        object."""
        jurisdictions = self.params.getlist("jurisdictions")
        years = self.params.getlist("years")

        if years:
            search.add_filter("year", years)

        if jurisdictions:
            search.add_filter("jurisdiction", jurisdictions)

        return search
