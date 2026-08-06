import datetime
import json

from django import forms

from peachjam.resources import DownloadDocumentsResource
from peachjam_search.compiler import ElasticsearchSearchCompiler
from peachjam_search.models import SavedSearch, SearchFeedback
from peachjam_search.search_pipeline import SearchQuery
from peachjam_search.serializers import PortionSearchRequestSerializer


class SearchForm(forms.Form):
    search = forms.CharField(required=False)
    page = forms.IntegerField(required=False, min_value=1, max_value=10)
    ordering = forms.ChoiceField(
        required=False, choices=[(x, x) for x in ["-score", "date", "-date"]]
    )
    date = forms.CharField(required=False)
    created_at = forms.CharField(required=False)
    mode = forms.ChoiceField(
        required=False, choices=[(x, x) for x in ["text", "semantic", "hybrid"]]
    )
    facets = forms.BooleanField(required=False)
    format = forms.ChoiceField(
        required=False,
        choices=[(x, x) for x in DownloadDocumentsResource.download_formats.keys()],
    )

    def clean_date(self):
        return self.clean_date_range("date", datetime.date.fromisoformat)

    def clean_created_at(self):
        return self.clean_date_range("created_at", datetime.datetime.fromisoformat)

    def clean_date_range(self, field, parser):
        def is_valid(date_string):
            try:
                parser(date_string)
                return True
            except ValueError:
                return False

        val = self.data.get(f"{field}__range")
        if val:
            if "__" in val:
                val = val.split("__", 2)
                if all(is_valid(x) for x in val):
                    return val
            return None

        val = self.data.get(f"{field}__gte")
        if val and is_valid(val):
            return [val, None]

        val = self.data.get(f"{field}__lte")
        if val and is_valid(val):
            return [None, val]

        val = self.data.get(field)
        if val and is_valid(val):
            return [val, val]

        if field == "date" and val and len(val) == 4 and val.isdigit():
            return [f"{val}-01-01", f"{val}-12-31"]

    def build_search_query(self, mode="text") -> SearchQuery:
        filters = {}

        for key in self.data.keys():
            if (
                key in ElasticsearchSearchCompiler.filter_fields
                and key not in ElasticsearchSearchCompiler.range_filter_fields
            ):
                vals = [x.strip() for x in self.data.getlist(key) if x.strip()]
                if vals:
                    filters[key] = vals

        # range fields (eg. dates) handled separately, can't be lists
        for field in ElasticsearchSearchCompiler.range_filter_fields:
            val = self.cleaned_data.get(field)
            if val:
                filters[field] = val

        field_queries = {}
        for field in ElasticsearchSearchCompiler.advanced_search_field_names() + [
            "all"
        ]:
            val = (self.data.get(f"search__{field}") or "").strip()
            if val:
                field_queries[field] = val

        return SearchQuery(
            query=self.cleaned_data.get("search"),
            field_queries=field_queries,
            mode=mode,
            filters=filters,
            facets=(
                list(SearchQuery.default_facets)
                if self.cleaned_data.get("facets")
                else []
            ),
            page=self.cleaned_data.get("page") or 1,
            page_size=SearchQuery.default_page_size,
            ordering=self.cleaned_data.get("ordering") or "-score",
            explain=False,
        )

    def configure_engine(self, engine):
        """Compatibility bridge for legacy callers.

        New callers should pass ``build_search_query()`` to ``SearchEngine``
        directly.  This method replaces the complete input rather than
        copying individual form values onto an engine.
        """
        engine.set_search_query(self.build_search_query())


class DocumentSearchDebugForm(SearchForm):
    query_params = forms.CharField(required=False)


class PortionSearchDebugForm(forms.Form):
    text = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    top_k = forms.IntegerField(
        required=True,
        min_value=1,
        max_value=100,
        initial=10,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    pre_filters = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"class": "form-control font-monospace", "rows": 5}
        ),
    )
    filters = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"class": "form-control font-monospace", "rows": 5}
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        if self.errors:
            return cleaned_data

        data = {
            "text": cleaned_data["text"],
            "top_k": cleaned_data["top_k"],
        }

        for field in ["pre_filters", "filters"]:
            raw = cleaned_data.get(field)
            if raw:
                try:
                    data[field] = json.loads(raw)
                except json.JSONDecodeError as e:
                    self.add_error(field, forms.ValidationError(f"Invalid JSON: {e}"))

        if self.errors:
            return cleaned_data

        serializer = PortionSearchRequestSerializer(data=data)
        if not serializer.is_valid():
            for field, errors in serializer.errors.items():
                form_field = field if field in self.fields else None
                self.add_error(form_field, errors)
            return cleaned_data

        cleaned_data["validated_portion_search"] = serializer.validated_data
        return cleaned_data


class RawSearchDebugForm(forms.Form):
    max_size = 25

    query = forms.CharField(
        required=True,
        widget=forms.Textarea(
            attrs={"class": "form-control font-monospace", "rows": 16}
        ),
    )
    size = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=max_size,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text=f"Optional result size override, maximum {max_size}.",
    )

    def clean_query(self):
        raw = self.cleaned_data["query"]
        try:
            query = json.loads(raw)
        except json.JSONDecodeError as e:
            raise forms.ValidationError(f"Invalid JSON: {e}")

        if not isinstance(query, dict):
            raise forms.ValidationError("Query must be a JSON object.")

        size = query.get("size")
        if size is not None:
            if not isinstance(size, int):
                raise forms.ValidationError("Query size must be an integer.")
            if size > self.max_size:
                raise forms.ValidationError(
                    f"Query size must be {self.max_size} or less."
                )

        return query


class SavedSearchCreateForm(forms.ModelForm):
    class Meta:
        model = SavedSearch
        fields = ["q", "a", "filters", "note"]


class SavedSearchUpdateForm(forms.ModelForm):
    class Meta:
        model = SavedSearch
        fields = ["note"]


class SearchFeedbackCreateForm(forms.ModelForm):
    class Meta:
        model = SearchFeedback
        fields = ["name", "email", "search_trace", "feedback"]
