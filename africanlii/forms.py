from dal import autocomplete
from django import forms

from peachjam.forms import BaseDocumentFilterForm
from peachjam.models import Ratification


class ESDocumentFilterForm(BaseDocumentFilterForm):
    """Form for filtering documents in Elasticsearch. Only applies a subset of filters."""

    def filter_queryset(self, search, exclude=None, filter_q=False):
        alphabet = self.cleaned_data.get("alphabet")
        jurisdictions = self.params.getlist("jurisdictions")
        years = self.params.getlist("years")
        q = self.params.get("q")
        if not isinstance(exclude, list):
            exclude = [exclude]

        search = self.order_queryset(search, exclude)

        if alphabet and "alphabet" not in exclude:
            search = search.filter(
                "prefix", title_keyword={"value": alphabet, "case_insensitive": True}
            )

        if jurisdictions and "jurisdictions" not in exclude:
            search = search.filter("terms", jurisdiction=jurisdictions)

        if years and "years" not in exclude:
            search = search.filter("terms", year=years)

        if filter_q and q and "q" not in exclude:
            search = search.query("match", title=q)

        return search

    def order_queryset(self, queryset, exclude=None):
        sort = self.cleaned_data.get("sort") or "-date"
        if sort == "title":
            sort = "title_keyword"
        elif sort == "-title":
            sort = "-title_keyword"
        queryset = queryset.sort(sort, "title_keyword")
        return queryset

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


class RatificationForm(forms.ModelForm):
    class Meta:
        model = Ratification
        fields = "__all__"
        widgets = {"work": autocomplete.ModelSelect2(url="autocomplete-works")}
