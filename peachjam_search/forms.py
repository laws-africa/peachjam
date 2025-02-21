import datetime

from django import forms

from peachjam_search.models import SavedSearch, SearchFeedback


class SearchForm(forms.Form):
    search = forms.CharField(required=False)
    page = forms.IntegerField(required=False, min_value=1, max_value=10)
    ordering = forms.ChoiceField(
        required=False, choices=[(x, x) for x in ["-score", "date", "-date"]]
    )
    date = forms.CharField(required=False)

    def clean_ordering(self):
        if self.cleaned_data["ordering"] == "-score":
            return "_score"
        return self.cleaned_data["ordering"]

    def clean_date(self):
        def is_valid(date_string):
            try:
                datetime.datetime.strptime(date_string, "%Y-%m-%d")
                return True
            except ValueError:
                return False

        val = self.data.get("date__range")
        if val:
            if "__" in val:
                val = val.split("__", 2)
                if all(is_valid(x) for x in val):
                    return val
            return None

        val = self.data.get("date__gte")
        if val and is_valid(val):
            return [val, None]

        val = self.data.get("date__lte")
        if val and is_valid(val):
            return [None, val]

    def configure_engine(self, engine):
        engine.query = self.cleaned_data.get("search")
        engine.page = self.cleaned_data.get("page") or 1
        engine.ordering = self.cleaned_data.get("ordering") or engine.ordering

        for key in self.data.keys():
            if key in engine.filter_fields:
                vals = [x.strip() for x in self.data.getlist(key) if x.strip()]
                if vals:
                    engine.filters[key] = vals

        # date ranges handled separately
        date = self.cleaned_data.get("date")
        if date:
            engine.filters["date"] = date

        for field in list(engine.advanced_search_fields.keys()) + ["all"]:
            val = (self.data.get(f"search__{field}") or "").strip()
            if val:
                engine.field_queries[field] = val


class SavedSearchCreateForm(forms.ModelForm):
    class Meta:
        model = SavedSearch
        fields = ["q", "filters", "note"]


class SavedSearchUpdateForm(forms.ModelForm):
    class Meta:
        model = SavedSearch
        fields = ["note"]


class SearchFeedbackCreateForm(forms.ModelForm):
    class Meta:
        model = SearchFeedback
        fields = ["name", "email", "search_trace", "feedback"]
